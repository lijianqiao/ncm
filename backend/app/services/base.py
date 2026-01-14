"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2026-01-15 10:00:00
@Docs: 服务层基类和 Mixin (Service Base Classes and Mixins).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_user_permissions_cache
from app.core.enums import AuthType
from app.core.exceptions import BadRequestException
from app.core.otp_service import otp_service
from app.crud.crud_credential import CRUDCredential
from app.models.device import Device
from app.schemas.credential import DeviceCredential


class PermissionCacheMixin:
    """
    权限缓存失效 Mixin。

    提供统一的权限缓存失效机制，供需要在事务提交后清理缓存的服务使用。
    配合 @transactional() 装饰器使用，装饰器会在 commit 后执行 _post_commit_tasks。

    Usage:
        class MyService(PermissionCacheMixin):
            def __init__(self, db: AsyncSession, ...):
                self.db = db
                self._post_commit_tasks: list = []  # 必须初始化

            @transactional()
            async def update_something(self, ...):
                # ... 业务逻辑 ...
                self._invalidate_permissions_cache_after_commit([user_id])
    """

    _post_commit_tasks: list

    def _invalidate_permissions_cache_after_commit(self, user_ids: list[UUID]) -> None:
        """
        注册权限缓存失效任务，在事务提交后执行。

        Args:
            user_ids: 需要失效缓存的用户 ID 列表。传空列表表示全局失效。
        """

        async def _task() -> None:
            await invalidate_user_permissions_cache(user_ids)

        self._post_commit_tasks.append(_task)


class DeviceCredentialMixin:
    """
    设备凭据获取 Mixin。

    提供统一的设备凭据获取逻辑，支持三种认证类型：
    - STATIC: 静态密码（从设备记录解密）
    - OTP_SEED: OTP 种子（从 DeviceGroupCredential 获取种子生成 TOTP）
    - OTP_MANUAL: 手动 OTP（从 Redis 缓存获取用户输入的 OTP）

    Usage:
        class MyService(DeviceCredentialMixin):
            def __init__(self, db: AsyncSession, credential_crud: CRUDCredential):
                self.db = db
                self.credential_crud = credential_crud

            async def do_something(self, device: Device):
                credential = await self._get_device_credential(device)
                # 使用 credential.username 和 credential.password
    """

    db: AsyncSession
    credential_crud: CRUDCredential

    async def _get_device_credential(
        self,
        device: Device,
        failed_devices: list[str] | None = None,
    ) -> DeviceCredential:
        """
        获取设备连接凭据。

        根据设备认证类型，从不同来源获取凭据：
        - static: 解密设备本身的密码
        - otp_seed: 从 DeviceGroupCredential 获取种子生成 TOTP
        - otp_manual: 从 Redis 缓存获取用户输入的 OTP

        Args:
            device: 设备对象
            failed_devices: 失败设备列表（断点续传用）

        Returns:
            DeviceCredential: 设备凭据

        Raises:
            OTPRequiredException: 需要用户输入 OTP（仅 otp_manual 模式）
            BadRequestException: 凭据配置缺失
        """
        auth_type = AuthType(device.auth_type)

        if auth_type == AuthType.STATIC:
            # 静态密码：从设备记录解密
            if not device.username or not device.password_encrypted:
                raise BadRequestException(message=f"设备 {device.name} 缺少用户名或密码配置")
            return await otp_service.get_credential_for_static_device(
                username=device.username,
                encrypted_password=device.password_encrypted,
            )

        elif auth_type == AuthType.OTP_SEED:
            # OTP 种子：从 DeviceGroupCredential 获取
            if not device.dept_id:
                raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")

            credential = await self.credential_crud.get_by_dept_and_group(self.db, device.dept_id, device.device_group)
            if not credential or not credential.otp_seed_encrypted:
                raise BadRequestException(message=f"设备 {device.name} 的凭据未配置 OTP 种子")

            return await otp_service.get_credential_for_otp_seed_device(
                username=credential.username,
                encrypted_seed=credential.otp_seed_encrypted,
            )

        elif auth_type == AuthType.OTP_MANUAL:
            # 手动 OTP：从 Redis 缓存获取
            if not device.dept_id:
                raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")

            credential = await self.credential_crud.get_by_dept_and_group(self.db, device.dept_id, device.device_group)
            if not credential:
                raise BadRequestException(message=f"设备 {device.name} 的凭据未配置")

            return await otp_service.get_credential_for_otp_manual_device(
                username=credential.username,
                dept_id=device.dept_id,
                device_group=device.device_group,
                failed_devices=failed_devices,
            )

        else:
            raise BadRequestException(message=f"不支持的认证类型: {auth_type}")
