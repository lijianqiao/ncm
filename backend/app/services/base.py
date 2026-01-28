"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2026-01-15 10:00:00
@Docs: 服务层基类和 Mixin (Service Base Classes and Mixins).
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache as cache_module
from app.core.cache import invalidate_cache, invalidate_user_permissions_cache
from app.core.enums import AuthType
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logger import logger
from app.core.otp_service import otp_service
from app.crud.base import CRUDBase
from app.crud.crud_credential import CRUDCredential
from app.models.device import Device
from app.schemas.common import BatchOperationResult
from app.schemas.credential import DeviceCredential


class BaseService:
    """
    服务基类，提供通用能力。

    提供以下功能：
    - 统一"获取并验证存在"模式
    - 统一批量操作结果构建
    - 事务后任务队列管理

    Usage:
        class MyService(BaseService):
            def __init__(self, db: AsyncSession, my_crud: CRUDMy):
                super().__init__(db)
                self.my_crud = my_crud

            async def get_item(self, item_id: UUID):
                return await self._get_or_raise(self.my_crud, item_id, entity_name="项目")
    """

    def __init__(self, db: AsyncSession):
        """
        初始化服务基类。

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self._post_commit_tasks: list = []

    async def _get_or_raise(
        self,
        crud: CRUDBase,
        id: UUID,
        *,
        entity_name: str = "记录",
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> Any:
        """
        获取记录，不存在则抛出 NotFoundException。

        Args:
            crud: CRUD 实例
            id: 记录 ID
            entity_name: 实体名称，用于错误消息
            is_deleted: 软删除过滤（False=未删除，True=已删除，None=全部）
            options: SQLAlchemy 加载选项

        Returns:
            查询到的记录

        Raises:
            NotFoundException: 记录不存在
        """
        obj = await crud.get(self.db, id=id, is_deleted=is_deleted, options=options)
        if not obj:
            raise NotFoundException(message=f"{entity_name}不存在")
        return obj

    @staticmethod
    def _build_batch_result(
        success_count: int,
        failed_ids: list[UUID],
        *,
        message: str = "操作完成",
    ) -> BatchOperationResult:
        """
        构建统一的批量操作结果。

        Args:
            success_count: 成功数量
            failed_ids: 失败的 ID 列表
            message: 操作结果消息

        Returns:
            BatchOperationResult: 批量操作结果
        """
        return BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=message,
        )


class CacheMixin:
    """
    缓存操作 Mixin。

    提供统一的 Redis 缓存操作，包括：
    - 获取缓存
    - 设置缓存（支持 TTL）
    - 删除缓存
    - 按模式删除缓存（使用 scan_iter，避免阻塞）

    Usage:
        class MyService(CacheMixin):
            async def get_data(self, key: str):
                cached = await self._cache_get(f"my:prefix:{key}")
                if cached:
                    return json.loads(cached)
                # ... 查询数据库 ...
                await self._cache_set(f"my:prefix:{key}", json.dumps(data), ttl=3600)
                return data
    """

    async def _cache_get(self, key: str) -> str | None:
        """
        获取缓存。

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        if cache_module.redis_client is None:
            return None
        try:
            return await cache_module.redis_client.get(key)
        except Exception as e:
            logger.warning(f"获取缓存失败 [{key}]: {e}")
            return None

    async def _cache_set(self, key: str, value: str, ttl: int) -> bool:
        """
        设置缓存。

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否设置成功
        """
        if cache_module.redis_client is None:
            return False
        try:
            await cache_module.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.warning(f"设置缓存失败 [{key}]: {e}")
            return False

    async def _cache_delete(self, *keys: str) -> int:
        """
        删除指定缓存。

        Args:
            keys: 要删除的缓存键

        Returns:
            删除的键数量
        """
        if cache_module.redis_client is None or not keys:
            return 0
        try:
            return await cache_module.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"删除缓存失败 {keys}: {e}")
            return 0

    async def _cache_delete_pattern(self, pattern: str) -> int:
        """
        删除匹配模式的缓存（复用 cache.py 的 invalidate_cache）。

        使用 scan_iter 遍历，避免 keys() 命令阻塞 Redis。

        Args:
            pattern: 匹配模式，如 "my:prefix:*"

        Returns:
            删除的键数量
        """
        return await invalidate_cache(pattern)


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
