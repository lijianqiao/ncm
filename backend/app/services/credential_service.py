"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credential_service.py
@DateTime: 2026-01-09 19:25:00
@Docs: 凭据服务业务逻辑 (Credential Service Logic).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.encryption import encrypt_otp_seed
from app.core.enums import AuthType, DeviceGroup
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.otp_service import otp_service
from app.crud.crud_credential import CRUDCredential
from app.models.credential import DeviceGroupCredential
from app.schemas.credential import (
    DeviceGroupCredentialCreate,
    DeviceGroupCredentialResponse,
    DeviceGroupCredentialUpdate,
    OTPCacheRequest,
    OTPCacheResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
)


class CredentialService:
    """
    凭据服务类。
    通过构造函数注入 CRUD 实例，实现解耦。
    """

    def __init__(self, db: AsyncSession, credential_crud: CRUDCredential):
        self.db = db
        self.credential_crud = credential_crud
        self._post_commit_tasks: list = []

    async def get_credentials_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        dept_id: UUID | None = None,
        device_group: DeviceGroup | None = None,
    ) -> tuple[list[DeviceGroupCredential], int]:
        """
        获取分页过滤的凭据列表。

        Args:
            page: 页码
            page_size: 每页数量
            dept_id: 部门筛选
            device_group: 设备分组筛选

        Returns:
            (items, total): 凭据列表和总数
        """
        return await self.credential_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            dept_id=dept_id,
            device_group=device_group.value if device_group else None,
        )

    async def get_credential(self, credential_id: UUID) -> DeviceGroupCredential:
        """
        根据 ID 获取凭据。

        Args:
            credential_id: 凭据ID

        Returns:
            DeviceGroupCredential: 凭据对象

        Raises:
            NotFoundException: 凭据不存在
        """
        credential = await self.credential_crud.get(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在")
        return credential

    async def get_credential_by_dept_and_group(
        self, dept_id: UUID, device_group: DeviceGroup
    ) -> DeviceGroupCredential | None:
        """
        根据部门和设备分组获取凭据。

        Args:
            dept_id: 部门ID
            device_group: 设备分组

        Returns:
            DeviceGroupCredential | None: 凭据对象或 None
        """
        return await self.credential_crud.get_by_dept_and_group(self.db, dept_id, device_group.value)

    @transactional()
    async def create_credential(self, obj_in: DeviceGroupCredentialCreate) -> DeviceGroupCredential:
        """
        创建凭据。

        Args:
            obj_in: 凭据创建数据

        Returns:
            DeviceGroupCredential: 创建的凭据

        Raises:
            BadRequestException: 凭据已存在或业务校验失败
        """
        # 1. 检查凭据唯一性
        if await self.credential_crud.exists_credential(self.db, obj_in.dept_id, obj_in.device_group.value):
            raise BadRequestException(
                message=f"部门 {obj_in.dept_id} 的设备分组 {obj_in.device_group.value} 凭据已存在"
            )

        # 2. OTP 种子认证类型校验
        if obj_in.auth_type == AuthType.OTP_SEED and not obj_in.otp_seed:
            raise BadRequestException(message="OTP 种子认证类型必须提供 OTP 种子")

        # 3. 准备创建数据
        create_data = obj_in.model_dump(exclude={"otp_seed"}, exclude_unset=True)
        create_data["device_group"] = obj_in.device_group.value
        create_data["auth_type"] = obj_in.auth_type.value

        # 4. 处理 OTP 种子加密
        if obj_in.otp_seed:
            create_data["otp_seed_encrypted"] = encrypt_otp_seed(obj_in.otp_seed)

        # 5. 创建凭据
        db_obj = DeviceGroupCredential(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    @transactional()
    async def update_credential(
        self, credential_id: UUID, obj_in: DeviceGroupCredentialUpdate
    ) -> DeviceGroupCredential:
        """
        更新凭据。

        Args:
            credential_id: 凭据ID
            obj_in: 凭据更新数据

        Returns:
            DeviceGroupCredential: 更新后的凭据

        Raises:
            NotFoundException: 凭据不存在
        """
        # 1. 获取凭据
        credential = await self.credential_crud.get(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在")

        # 2. 处理更新数据
        update_data = obj_in.model_dump(exclude={"otp_seed"}, exclude_unset=True)

        # 转换枚举值
        if obj_in.auth_type:
            update_data["auth_type"] = obj_in.auth_type.value

        # 3. 处理 OTP 种子加密（如果提供了新种子）
        if obj_in.otp_seed:
            update_data["otp_seed_encrypted"] = encrypt_otp_seed(obj_in.otp_seed)

        # 4. 更新凭据
        return await self.credential_crud.update(self.db, db_obj=credential, obj_in=update_data)

    @transactional()
    async def delete_credential(self, credential_id: UUID) -> DeviceGroupCredential:
        """
        删除凭据（软删除）。

        Args:
            credential_id: 凭据ID

        Returns:
            DeviceGroupCredential: 删除的凭据

        Raises:
            NotFoundException: 凭据不存在
        """
        credential = await self.credential_crud.get(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在")
        success_count, _ = await self.credential_crud.batch_remove(self.db, ids=[credential_id])
        if success_count == 0:
            raise NotFoundException(message="凭据不存在")
        # 刷新对象以获取最新状态（包括 is_deleted=True 和 updated_at）
        await self.db.refresh(credential)
        return credential

    @transactional()
    async def batch_delete_credentials(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量删除凭据（软删除）。

        Args:
            ids: 凭据ID列表

        Returns:
            (success_count, failed_ids): 成功数量和失败的ID列表
        """
        return await self.credential_crud.batch_remove(self.db, ids=ids, hard_delete=False)

    async def get_recycle_bin_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[DeviceGroupCredential], int]:
        """
        获取回收站凭据列表（分页）。

        Args:
            page: 页码
            page_size: 每页数量
            keyword: 关键字搜索

        Returns:
            (items, total): 已删除凭据列表和总数
        """
        return await self.credential_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
        )

    @transactional()
    async def restore_credential(self, credential_id: UUID) -> DeviceGroupCredential:
        """
        恢复已删除的凭据。

        Args:
            credential_id: 凭据ID

        Returns:
            DeviceGroupCredential: 恢复的凭据

        Raises:
            NotFoundException: 凭据不存在或未被删除
        """
        credential = await self.credential_crud.get_deleted(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在或未被删除")

        success_count, _ = await self.credential_crud.batch_restore(self.db, ids=[credential_id])
        if success_count == 0:
            raise NotFoundException(message="恢复失败")

        await self.db.refresh(credential)
        return credential

    @transactional()
    async def batch_restore_credentials(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量恢复已删除的凭据。

        Args:
            ids: 凭据ID列表

        Returns:
            (success_count, failed_ids): 成功数量和失败的ID列表
        """
        return await self.credential_crud.batch_restore(self.db, ids=ids)

    @transactional()
    async def hard_delete_credential(self, credential_id: UUID) -> None:
        """
        彻底删除凭据（硬删除）。

        Args:
            credential_id: 凭据ID

        Raises:
            NotFoundException: 凭据不存在
        """
        credential = await self.credential_crud.get_deleted(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在或未被软删除")

        success_count, _ = await self.credential_crud.batch_remove(self.db, ids=[credential_id], hard_delete=True)
        if success_count == 0:
            raise NotFoundException(message="彻底删除失败")

    @transactional()
    async def batch_hard_delete_credentials(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量彻底删除凭据（硬删除）。

        Args:
            ids: 凭据ID列表

        Returns:
            (success_count, failed_ids): 成功数量和失败的ID列表
        """
        return await self.credential_crud.batch_remove(self.db, ids=ids, hard_delete=True)

    async def cache_otp(self, request: OTPCacheRequest) -> OTPCacheResponse:
        """
        缓存用户输入的 OTP 验证码。

        Args:
            request: OTP 缓存请求

        Returns:
            OTPCacheResponse: 缓存响应

        Raises:
            BadRequestException: 当 Redis 未连接或缓存失败时抛出
        """
        from app.core.exceptions import BadRequestException

        try:
            ttl = await otp_service.cache_otp(request.dept_id, request.device_group, request.otp_code)
            # cache_otp 返回 0 表示 Redis 未连接或缓存失败
            if ttl == 0:
                raise BadRequestException(message="OTP 缓存失败：Redis 服务未连接，请联系管理员")
            return OTPCacheResponse(
                success=True,
                message="OTP 缓存成功",
                expires_in=ttl,
            )
        except BadRequestException:
            raise
        except Exception as e:
            raise BadRequestException(message=f"OTP 缓存失败: {str(e)}") from e

    async def verify_and_cache_otp(self, request: OTPVerifyRequest) -> OTPVerifyResponse:
        """
        验证并缓存 OTP 验证码。

        通过连接一台代表设备来验证 OTP 是否正确：
        1. 查找该部门+分组下一台 otp_manual 类型的设备
        2. 使用提供的 OTP 尝试连接该设备
        3. 连接成功 → 缓存 OTP → 返回成功
        4. 连接失败 → 不缓存 → 抛出 OTPRequiredException

        Args:
            request: OTP 验证请求

        Returns:
            OTPVerifyResponse: 验证结果

        Raises:
            BadRequestException: 找不到可测试的设备
            OTPRequiredException: OTP 验证失败
        """
        from scrapli import AsyncScrapli
        from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliConnectionError
        from sqlalchemy import select

        from app.core.exceptions import OTPRequiredException
        from app.core.logger import logger
        from app.crud.crud_credential import credential as credential_crud
        from app.models.device import Device
        from app.network.platform_config import get_platform_for_vendor, get_scrapli_options

        # 1. 查找一台代表设备（指定部门+分组+otp_manual）
        query = (
            select(Device)
            .where(Device.dept_id == request.dept_id)
            .where(Device.device_group == request.device_group.value)
            .where(Device.auth_type == AuthType.OTP_MANUAL.value)
            .where(Device.is_deleted.is_(False))
            .limit(1)
        )
        result = await self.db.execute(query)
        test_device = result.scalars().first()

        if not test_device:
            raise BadRequestException(
                message=f"该部门/分组下没有 otp_manual 类型的设备可供测试"
            )

        # 2. 获取该设备组的凭据（用户名）
        credential = await credential_crud.get_by_dept_and_group(
            self.db, request.dept_id, request.device_group.value
        )
        if not credential:
            raise BadRequestException(
                message=f"该部门/分组未配置凭据"
            )

        # 3. 构建 Scrapli 连接参数
        platform = get_platform_for_vendor(test_device.vendor or "hp_comware")
        base_options = get_scrapli_options(platform)

        scrapli_kwargs = {
            **base_options,
            "host": test_device.ip_address,
            "auth_username": credential.username,
            "auth_password": request.otp_code,
            "port": test_device.ssh_port or 22,
            "platform": platform,
            "transport": "asyncssh",  # 必须使用异步 transport
            "timeout_socket": 10,
            "timeout_transport": 15,
            "timeout_ops": 10,
        }

        # 4. 尝试连接设备验证 OTP
        logger.info(
            "OTP 验证：尝试连接设备",
            device=test_device.name,
            ip=test_device.ip_address,
            dept_id=str(request.dept_id),
            device_group=request.device_group.value,
        )

        try:
            conn = AsyncScrapli(**scrapli_kwargs)
            try:
                await conn.open()
                # 连接成功，获取提示符确认登录
                prompt = await conn.get_prompt()
                logger.info(
                    "OTP 验证成功",
                    device=test_device.name,
                    prompt=prompt[:50] if prompt else None,
                )
            finally:
                try:
                    await conn.close()
                except Exception:
                    pass

            # 5. 验证成功，缓存 OTP
            ttl = await otp_service.cache_otp(
                request.dept_id, request.device_group, request.otp_code
            )

            return OTPVerifyResponse(
                verified=True,
                message="OTP 验证成功",
                expires_in=ttl,
                device_tested=test_device.name,
            )

        except ScrapliAuthenticationFailed as e:
            # 认证失败，OTP 错误
            logger.warning(
                "OTP 验证失败：认证错误",
                device=test_device.name,
                error=str(e),
            )
            raise OTPRequiredException(
                dept_id=request.dept_id,
                device_group=request.device_group.value,
                failed_devices=[str(test_device.id)],
                message="OTP 验证失败，请检查验证码是否正确",
            )

        except (ScrapliConnectionError, TimeoutError, OSError) as e:
            # 连接失败（网络问题），不能确定 OTP 是否正确
            logger.warning(
                "OTP 验证失败：连接错误",
                device=test_device.name,
                error=str(e),
            )
            raise BadRequestException(
                message=f"无法连接测试设备 {test_device.name}，请检查网络或稍后重试"
            )

        except Exception as e:
            logger.error(
                "OTP 验证失败：未知错误",
                device=test_device.name,
                error=str(e),
                exc_info=True,
            )
            raise BadRequestException(
                message=f"OTP 验证过程中发生错误: {str(e)}"
            )

    def to_response(self, credential: DeviceGroupCredential) -> DeviceGroupCredentialResponse:
        """
        转换凭据模型为响应格式（隐藏敏感字段）。

        Args:
            credential: 凭据模型

        Returns:
            DeviceGroupCredentialResponse: 凭据响应
        """
        return DeviceGroupCredentialResponse(
            id=credential.id,
            dept_id=credential.dept_id,
            dept_name=credential.dept.name if credential.dept else None,
            device_group=credential.device_group,
            username=credential.username,
            auth_type=credential.auth_type,
            description=credential.description,
            has_otp_seed=bool(credential.otp_seed_encrypted),
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )
