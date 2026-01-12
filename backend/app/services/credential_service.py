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
        return await self.credential_crud.get_multi_paginated_filtered(
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
        credential = await self.credential_crud.remove(self.db, id=credential_id)
        if not credential:
            raise NotFoundException(message="凭据不存在")
        return credential

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
