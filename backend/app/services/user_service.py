"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: user_service.py
@DateTime: 2025-12-30 12:30:00
@Docs: 用户服务业务逻辑 (User Service Logic).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.decorator import transactional
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_role import CRUDRole
from app.crud.crud_user import CRUDUser
from app.models.rbac import Role
from app.models.user import User
from app.schemas.common import BatchOperationResult
from app.schemas.user import UserCreate, UserMeUpdate, UserUpdate
from app.services.base import BaseService, PermissionCacheMixin


class UserService(BaseService, PermissionCacheMixin):
    """
    用户服务类。
    通过构造函数注入 CRUDUser 实例，实现解耦。
    """

    def __init__(self, db: AsyncSession, user_crud: CRUDUser, role_crud: CRUDRole):
        super().__init__(db)
        self.user_crud = user_crud
        self.role_crud = role_crud

    @transactional()
    async def create_user(self, obj_in: UserCreate) -> User:
        # 1. 检查用户名
        user = await self.user_crud.get_by_unique_field(
            self.db,
            field="username",
            value=obj_in.username,
            include_deleted=True,
        )
        if user:
            if user.is_deleted:
                raise BadRequestException(message="该用户名已被注销/删除，请联系管理员恢复")
            raise BadRequestException(message="该用户名的用户已存在")

        # 2. 检查手机号
        user = await self.user_crud.get_by_unique_field(
            self.db,
            field="phone",
            value=obj_in.phone,
            include_deleted=True,
        )
        if user:
            if user.is_deleted:
                raise BadRequestException(message="该手机号已被注销/删除，请联系管理员恢复")
            raise BadRequestException(message="该手机号的用户已存在")

        # 3. 检查邮箱
        if obj_in.email:
            user = await self.user_crud.get_by_unique_field(
                self.db,
                field="email",
                value=obj_in.email,
                include_deleted=True,
            )
            if user:
                if user.is_deleted:
                    raise BadRequestException(message="该邮箱已被注销/删除，请联系管理员恢复")
                raise BadRequestException(message="该邮箱的用户已存在")

        created_user = await self.user_crud.create(self.db, obj_in=obj_in)

        # 默认角色：非超级管理员创建后自动绑定一个基础角色
        if not created_user.is_superuser:
            default_role_code = (settings.DEFAULT_USER_ROLE_CODE or "").strip()
            if default_role_code:
                default_role = await self.role_crud.get_by_code(self.db, code=default_role_code)
                if default_role and default_role.is_active and not default_role.is_deleted:
                    created_user.roles = [default_role]
                    self.db.add(created_user)
                    await self.db.flush()

        return created_user

    async def get_user(self, user_id: UUID) -> User | None:
        """
        根据 ID 获取用户。
        """
        return await self.user_crud.get(self.db, id=user_id)

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        """获取用户的角色列表。"""

        user = await self.user_crud.get_with_roles(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")
        return list(user.roles)

    async def get_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """
        获取用户列表 (分页)。
        """
        # 使用分页查询替代 get_multi
        page = (skip // limit) + 1 if limit > 0 else 1
        users, _ = await self.user_crud.get_multi_paginated(self.db, page=page, page_size=limit)
        return users

    async def get_users_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_superuser: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """
        获取分页用户列表。

        Returns:
            (users, total): 用户列表和总数
        """
        return await self.user_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_superuser=is_superuser,
            is_active=is_active,
        )

    async def get_deleted_users(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_superuser: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """
        获取已删除用户列表 (回收站 - 分页)。
        """
        return await self.user_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_superuser=is_superuser,
            is_active=is_active,
        )

    @transactional()
    async def set_user_roles(self, user_id: UUID, role_ids: list[UUID]) -> list[Role]:
        """设置用户角色（全量覆盖，幂等）。"""

        user = await self.user_crud.get_with_roles(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        unique_role_ids = list(dict.fromkeys(role_ids))
        roles = await self.role_crud.get_by_ids(self.db, unique_role_ids, options=self.role_crud._ROLE_OPTIONS)

        if len(roles) != len(unique_role_ids):
            found = {r.id for r in roles}
            missing = [rid for rid in unique_role_ids if rid not in found]
            raise BadRequestException(message=f"存在无效的角色ID: {missing}")

        user.roles = roles
        self._invalidate_permissions_cache_after_commit([user.id])
        return roles

    @transactional()
    async def update_user_me(self, user_id: UUID, obj_in: UserMeUpdate) -> User:
        """更新当前用户信息（不允许修改 username）。"""

        user = await self.user_crud.get(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        update_data = obj_in.model_dump(exclude_unset=True)

        if "phone" in update_data and update_data["phone"] != user.phone:
            if await self.user_crud.get_by_unique_field(self.db, field="phone", value=update_data["phone"]):
                raise BadRequestException(message="手机号已存在")

        if "email" in update_data and update_data["email"] != user.email:
            if await self.user_crud.get_by_unique_field(self.db, field="email", value=update_data["email"]):
                raise BadRequestException(message="邮箱已存在")

        return await self.user_crud.update(self.db, db_obj=user, obj_in=update_data)

    @transactional()
    async def update_user(self, user_id: UUID, obj_in: UserUpdate) -> User:
        """
        更新用户信息。
        """
        user = await self.user_crud.get(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        # 唯一性检查
        if obj_in.username is not None and obj_in.username != user.username:
            if await self.user_crud.get_by_unique_field(self.db, field="username", value=obj_in.username):
                raise BadRequestException(message="用户名已存在")

        if obj_in.phone is not None and obj_in.phone != user.phone:
            if await self.user_crud.get_by_unique_field(self.db, field="phone", value=obj_in.phone):
                raise BadRequestException(message="手机号已存在")

        if obj_in.email is not None and obj_in.email != user.email:
            if await self.user_crud.get_by_unique_field(self.db, field="email", value=obj_in.email):
                raise BadRequestException(message="邮箱已存在")

        return await self.user_crud.update(self.db, db_obj=user, obj_in=obj_in)

    @transactional()
    async def change_password(self, user_id: UUID, old_password: str, new_password: str) -> User:
        """
        用户修改自己的密码 (需验证旧密码)。
        """
        user = await self.user_crud.get(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        if not security.verify_password(old_password, user.password):
            raise BadRequestException(message="旧密码错误")

        # 传递明文密码，CRUD 层会处理哈希
        return await self.user_crud.update(self.db, db_obj=user, obj_in={"password": new_password})

    @transactional()
    async def reset_password(self, user_id: UUID, new_password: str) -> User:
        """
        管理员重置用户密码 (无需验证旧密码)。
        """
        user = await self.user_crud.get(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        # 传递明文密码，CRUD 层会处理哈希
        return await self.user_crud.update(self.db, db_obj=user, obj_in={"password": new_password})

    @transactional()
    async def batch_delete_users(self, ids: list[UUID], hard_delete: bool = False) -> BatchOperationResult:
        """
        批量删除用户。

        Args:
            ids: 要删除的用户 ID 列表
            hard_delete: 是否硬删除

        Returns:
            BatchOperationResult: 批量操作结果
        """
        success_count, failed_ids = await self.user_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)
        return self._build_batch_result(success_count, failed_ids, message="删除完成")

    @transactional()
    async def restore_user(self, id: UUID) -> User:
        """
        恢复已删除用户。
        """
        success_count, _ = await self.user_crud.batch_restore(self.db, ids=[id])
        if success_count == 0:
            raise NotFoundException(message="用户不存在")
        # 重新获取用户对象返回
        user = await self.user_crud.get(self.db, id=id)
        if not user:
            raise NotFoundException(message="用户不存在")
        return user

    @transactional()
    async def batch_restore_users(self, ids: list[UUID]) -> BatchOperationResult:
        """批量恢复用户。"""
        success_count, failed_ids = await self.user_crud.batch_restore(self.db, ids=ids)
        return self._build_batch_result(success_count, failed_ids, message="恢复完成")
