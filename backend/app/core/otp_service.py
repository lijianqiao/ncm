"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: otp_service.py
@DateTime: 2026-01-09 17:00:00
@Docs: OTP 认证服务模块。

支持三种认证模式：
1. static: 静态密码（从设备表解密）
2. otp_seed: OTP 种子自动生成（从 DeviceGroupCredential 解密种子后 PyOTP 生成）
3. otp_manual: OTP 手动输入（从 Redis 缓存获取用户输入的 OTP）
"""

from uuid import UUID

import pyotp

from app.core.cache import redis_client
from app.core.encryption import decrypt_otp_seed, decrypt_password
from app.core.enums import AuthType
from app.core.exceptions import DeviceCredentialNotFoundException, OTPRequiredException
from app.core.logger import logger
from app.schemas.credential import DeviceCredential

# OTP 缓存配置
OTP_CACHE_PREFIX = "ncm:otp"
OTP_CACHE_TTL = 60  # 60 秒


class OTPService:
    """
    OTP 认证服务。

    提供 TOTP 验证码生成、OTP 缓存管理、设备凭据获取等功能。
    """

    def __init__(self, cache_ttl: int = OTP_CACHE_TTL):
        """
        初始化 OTP 服务。

        Args:
            cache_ttl: OTP 缓存过期时间（秒），默认 60 秒
        """
        self.cache_ttl = cache_ttl

    # ===== TOTP 生成 =====

    def generate_totp(self, encrypted_seed: str) -> str:
        """
        从加密的 OTP 种子生成当前 TOTP 验证码。

        Args:
            encrypted_seed: AES-256-GCM 加密后的 OTP 种子

        Returns:
            6 位 TOTP 验证码

        Raises:
            DecryptionError: 种子解密失败
        """
        # 解密种子
        seed = decrypt_otp_seed(encrypted_seed)
        # 生成 TOTP
        totp = pyotp.TOTP(seed)
        return totp.now()

    def verify_totp(self, encrypted_seed: str, otp_code: str) -> bool:
        """
        验证 TOTP 验证码是否正确。

        Args:
            encrypted_seed: 加密的 OTP 种子
            otp_code: 用户输入的验证码

        Returns:
            验证是否通过
        """
        seed = decrypt_otp_seed(encrypted_seed)
        totp = pyotp.TOTP(seed)
        return totp.verify(otp_code)

    # ===== OTP 缓存管理 =====

    def _get_cache_key(self, dept_id: UUID, device_group: str) -> str:
        """生成 OTP 缓存键。"""
        return f"{OTP_CACHE_PREFIX}:{dept_id}:{device_group}"

    async def cache_otp(
        self,
        dept_id: UUID,
        device_group: str,
        otp_code: str,
    ) -> int:
        """
        缓存用户输入的 OTP 验证码。

        Args:
            dept_id: 部门 ID
            device_group: 设备分组（core/distribution/access）
            otp_code: OTP 验证码

        Returns:
            缓存剩余有效期（秒）

        Note:
            - 缓存键格式: ncm:otp:{dept_id}:{device_group}
            - TTL: 60 秒
            - 同一部门下不同设备分组的 OTP 相互隔离
        """
        if redis_client is None:
            logger.warning("Redis 未连接，OTP 缓存功能不可用")
            return 0

        cache_key = self._get_cache_key(dept_id, device_group)

        try:
            await redis_client.setex(cache_key, self.cache_ttl, otp_code)
            logger.info(f"OTP 已缓存: {cache_key}, TTL={self.cache_ttl}s")
            return self.cache_ttl
        except Exception as e:
            logger.error(f"OTP 缓存失败: {e}")
            return 0

    async def get_cached_otp(self, dept_id: UUID, device_group: str) -> str | None:
        """
        获取缓存的 OTP 验证码。

        Args:
            dept_id: 部门 ID
            device_group: 设备分组

        Returns:
            缓存的 OTP 验证码，不存在或过期返回 None
        """
        if redis_client is None:
            return None

        cache_key = self._get_cache_key(dept_id, device_group)

        try:
            otp_code = await redis_client.get(cache_key)
            if otp_code:
                logger.debug(f"OTP 缓存命中: {cache_key}")
            return otp_code
        except Exception as e:
            logger.error(f"OTP 缓存读取失败: {e}")
            return None

    async def get_otp_ttl(self, dept_id: UUID, device_group: str) -> int:
        """
        获取 OTP 缓存剩余有效期。

        Args:
            dept_id: 部门 ID
            device_group: 设备分组

        Returns:
            剩余秒数，不存在返回 -2，无过期时间返回 -1
        """
        if redis_client is None:
            return -2

        cache_key = self._get_cache_key(dept_id, device_group)

        try:
            ttl = await redis_client.ttl(cache_key)
            return ttl
        except Exception as e:
            logger.error(f"获取 OTP TTL 失败: {e}")
            return -2

    async def invalidate_otp(self, dept_id: UUID, device_group: str) -> bool:
        """
        使 OTP 缓存失效（认证失败时调用）。

        Args:
            dept_id: 部门 ID
            device_group: 设备分组

        Returns:
            是否成功删除
        """
        if redis_client is None:
            return False

        cache_key = self._get_cache_key(dept_id, device_group)

        try:
            deleted = await redis_client.delete(cache_key)
            if deleted:
                logger.info(f"OTP 缓存已失效: {cache_key}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"OTP 缓存失效失败: {e}")
            return False

    # ===== 设备凭据获取 =====

    async def get_credential_for_static_device(
        self,
        username: str,
        encrypted_password: str,
    ) -> DeviceCredential:
        """
        获取静态密码设备的凭据。

        Args:
            username: 用户名
            encrypted_password: 加密的密码

        Returns:
            设备凭据
        """
        password = decrypt_password(encrypted_password)
        return DeviceCredential(
            username=username,
            password=password,
            auth_type=AuthType.STATIC,
        )

    async def get_credential_for_otp_seed_device(
        self,
        username: str,
        encrypted_seed: str,
    ) -> DeviceCredential:
        """
        获取 OTP 种子设备的凭据（自动生成验证码）。

        Args:
            username: 用户名
            encrypted_seed: 加密的 OTP 种子

        Returns:
            设备凭据（包含自动生成的 TOTP）
        """
        otp_code = self.generate_totp(encrypted_seed)
        return DeviceCredential(
            username=username,
            password=otp_code,
            auth_type=AuthType.OTP_SEED,
        )

    async def get_credential_for_otp_manual_device(
        self,
        username: str,
        dept_id: UUID,
        device_group: str,
        failed_devices: list[str] | None = None,
    ) -> DeviceCredential:
        """
        获取手动输入 OTP 设备的凭据（从缓存获取）。

        Args:
            username: 用户名
            dept_id: 部门 ID
            device_group: 设备分组
            failed_devices: 失败设备列表（用于断点续传）

        Returns:
            设备凭据

        Raises:
            OTPRequiredException: 缓存中没有有效 OTP，需要用户输入
        """
        otp_code = await self.get_cached_otp(dept_id, device_group)

        if otp_code is None:
            raise OTPRequiredException(
                dept_id=dept_id,
                device_group=device_group,
                failed_devices=failed_devices,
                message=f"需要输入 OTP 验证码 (部门={dept_id}, 分组={device_group})",
            )

        return DeviceCredential(
            username=username,
            password=otp_code,
            auth_type=AuthType.OTP_MANUAL,
        )

    async def get_device_credential(
        self,
        auth_type: AuthType,
        username: str,
        password_or_seed: str | None = None,
        dept_id: UUID | None = None,
        device_group: str | None = None,
        failed_devices: list[str] | None = None,
    ) -> DeviceCredential:
        """
        获取设备连接凭据（统一入口）。

        根据认证类型自动选择凭据获取方式：
        - static: 解密静态密码
        - otp_seed: 从种子生成 TOTP
        - otp_manual: 从缓存获取用户输入的 OTP

        Args:
            auth_type: 认证类型
            username: 用户名
            password_or_seed: 加密的密码（static）或 OTP 种子（otp_seed）
            dept_id: 部门 ID（otp_manual 必需）
            device_group: 设备分组（otp_manual 必需）
            failed_devices: 失败设备列表（断点续传用）

        Returns:
            设备凭据

        Raises:
            OTPRequiredException: 需要用户输入 OTP
            DeviceCredentialNotFoundException: 凭据配置缺失
        """
        if auth_type == AuthType.STATIC:
            if not password_or_seed:
                raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")
            return await self.get_credential_for_static_device(username, password_or_seed)

        elif auth_type == AuthType.OTP_SEED:
            if not password_or_seed:
                raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")
            return await self.get_credential_for_otp_seed_device(username, password_or_seed)

        elif auth_type == AuthType.OTP_MANUAL:
            if dept_id is None or device_group is None:
                raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")
            return await self.get_credential_for_otp_manual_device(
                username, dept_id, device_group, failed_devices
            )

        else:
            raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")


# 全局单例
otp_service = OTPService()
