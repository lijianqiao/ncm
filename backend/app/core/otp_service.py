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

from app.core import cache as cache_module  # 使用模块引用，避免导入时获取 None
from app.core.config import settings
from app.core.encryption import decrypt_otp_seed, decrypt_password
from app.core.enums import AuthType
from app.core.exceptions import DeviceCredentialNotFoundException, OTPRequiredException
from app.core.logger import logger
from app.core.otp import otp_coordinator
from app.core.otp.storage import otp_cache_key_by_credential
from app.schemas.credential import DeviceCredential


class OTPService:
    """
    OTP 认证服务。

    提供 TOTP 验证码生成、OTP 缓存管理、设备凭据获取等功能。
    """

    def __init__(self, cache_ttl: int = settings.OTP_CACHE_TTL_SECONDS):
        """
        初始化 OTP 服务。

        Args:
            cache_ttl: OTP 缓存过期时间（秒）
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

    async def cache_otp(
        self,
        credential_id: UUID,
        otp_code: str,
    ) -> int:
        """
        缓存用户输入的 OTP 验证码。

        Args:
            credential_id: 设备凭据 ID
            otp_code: OTP 验证码

        Returns:
            缓存剩余有效期（秒）

        Note:
            - 新缓存键格式: ncm:otp:v2:cache:{credential_id}
            - TTL: 由配置项控制
        """
        return await otp_coordinator.cache_otp(credential_id, otp_code)

    async def get_cached_otp(
        self,
        credential_id: UUID,
    ) -> str | None:
        """
        获取缓存的 OTP 验证码。

        Args:
            credential_id: 设备凭据 ID

        Returns:
            缓存的 OTP 验证码，不存在或过期返回 None
        """
        return await otp_coordinator.get_cached_otp(credential_id)

    async def get_otp_ttl(
        self,
        credential_id: UUID,
    ) -> int:
        """
        获取 OTP 缓存剩余有效期。

        Args:
            credential_id: 设备凭据 ID

        Returns:
            剩余秒数，不存在返回 -2，无过期时间返回 -1
        """
        client = cache_module.redis_client
        if client is None:
            return -2
        cache_key = otp_cache_key_by_credential(credential_id)
        try:
            ttl = await client.ttl(cache_key)
            if ttl is not None and ttl >= 0:
                return ttl
        except Exception as e:
            logger.error(f"获取 OTP TTL 失败: {e}")
            return -2

        return -2

    async def invalidate_otp(
        self,
        credential_id: UUID,
    ) -> bool:
        """
        使 OTP 缓存失效（认证失败时调用）。

        Args:
            credential_id: 设备凭据 ID

        Returns:
            是否成功删除
        """
        await otp_coordinator.invalidate_otp(credential_id)
        logger.info("OTP 缓存已失效", credential_id=str(credential_id))
        return True

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
        credential_id: UUID,
        credential_device_group: str | None = None,
        failed_devices: list[str] | None = None,
    ) -> DeviceCredential:
        """
        获取手动输入 OTP 设备的凭据（从缓存获取）。

        Args:
            username: 用户名
            credential_id: 设备凭据 ID
            credential_device_group: 凭据对应的设备分组
            failed_devices: 失败设备列表（用于断点续传）

        Returns:
            设备凭据

        Raises:
            OTPRequiredException: 缓存中没有有效 OTP，需要用户输入
        """
        result = await otp_coordinator.get_or_require_otp(
            credential_id,
            pending_device_ids=failed_devices,
        )

        if result["status"] != "ready" or not result["otp_code"]:
            message = "用户未提供 OTP 验证码，连接失败" if result["status"] == "timeout" else "需要输入 OTP 验证码"
            raise OTPRequiredException(
                credential_id=credential_id,
                failed_devices=failed_devices,
                pending_device_ids=failed_devices,
                message=message,
                otp_wait_status=result["status"],
                credential_username=username,
                credential_device_group=credential_device_group,
            )

        return DeviceCredential(
            username=username,
            password=result["otp_code"],
            auth_type=AuthType.OTP_MANUAL,
        )

    async def get_device_credential(
        self,
        auth_type: AuthType,
        username: str,
        password_or_seed: str | None = None,
        credential_id: UUID | None = None,
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
            credential_id: 凭据 ID（otp_manual 必需）
            dept_id: 部门 ID（兼容字段）
            device_group: 设备分组（兼容字段）
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
            if credential_id is None:
                raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")
            return await self.get_credential_for_otp_manual_device(
                username,
                credential_id,
                credential_device_group=device_group,
                failed_devices=failed_devices,
            )

        else:
            raise DeviceCredentialNotFoundException(dept_id, device_group or "unknown")


# 全局单例
otp_service = OTPService()
