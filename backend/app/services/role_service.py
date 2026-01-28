"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: role_service.py
@DateTime: 2025-12-30 14:50:00
@Docs: 角色服务业务逻辑 (Role Service Logic).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_menu import CRUDMenu
from app.crud.crud_role import CRUDRole
from app.models.rbac import Role
from app.schemas.common import BatchOperationResult
from app.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from app.services.base import BaseService, PermissionCacheMixin


class RoleService(BaseService, PermissionCacheMixin):
    """
    角色服务类。
    """

    def __init__(self, db: AsyncSession, role_crud: CRUDRole, menu_crud: CRUDMenu):
        super().__init__(db)
        self.role_crud = role_crud
        self.menu_crud = menu_crud

    async def get_roles(self, skip: int = 0, limit: int = 100) -> list[Role]:
        # 使用分页查询替代 get_multi
        page = (skip // limit) + 1 if limit > 0 else 1
        roles, _ = await self.role_crud.get_multi_paginated(self.db, page=page, page_size=limit)
        return roles

    async def get_role_menu_ids(self, role_id: UUID) -> list[UUID]:
        """获取角色已分配的菜单ID列表（仅未删除菜单）。"""

        role = await self.role_crud.get(self.db, id=role_id)
        if not role:
            raise NotFoundException(message="角色不存在")
        return [m.id for m in role.menus if not m.is_deleted]

    async def get_roles_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Role], int]:
        """
        获取分页角色列表。
        """
        return await self.role_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
        )

    async def get_deleted_roles(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Role], int]:
        """
        获取已删除角色列表 (回收站 - 分页)。
        """
        return await self.role_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
        )

    @transactional()
    async def create_role(self, obj_in: RoleCreate) -> Role:
        existing_role = await self.role_crud.get_by_code(self.db, code=obj_in.code)
        if existing_role:
            raise BadRequestException(message="角色编码已存在")

        role = await self.role_crud.create(self.db, obj_in=obj_in)
        self._invalidate_permissions_cache_after_commit([])
        return role

    @transactional()
    async def set_role_menus(self, role_id: UUID, menu_ids: list[UUID]) -> list[UUID]:
        """设置角色菜单（全量覆盖，幂等）。"""

        role = await self.role_crud.get(self.db, id=role_id)
        if not role:
            raise NotFoundException(message="角色不存在")

        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=[role_id])

        unique_menu_ids = list(dict.fromkeys(menu_ids))
        menus = await self.menu_crud.get_by_ids(self.db, unique_menu_ids)
        if len(menus) != len(unique_menu_ids):
            found = {m.id for m in menus}
            missing = [mid for mid in unique_menu_ids if mid not in found]
            raise BadRequestException(message=f"存在无效的菜单ID: {missing}")

        await self.role_crud.update(self.db, db_obj=role, obj_in={"menu_ids": unique_menu_ids})
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return unique_menu_ids

    @transactional()
    async def update_role(self, id: UUID, obj_in: RoleUpdate) -> Role:
        role = await self.role_crud.get(self.db, id=id)
        if not role:
            raise NotFoundException(message="角色不存在")

        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=[id])

        if obj_in.code:
            existing_role = await self.role_crud.get_by_code(self.db, code=obj_in.code)
            if existing_role and existing_role.id != id:
                raise BadRequestException(message="角色编码被占用")

        updated = await self.role_crud.update(self.db, db_obj=role, obj_in=obj_in)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return updated

    @transactional()
    async def delete_role(self, id: UUID) -> RoleResponse:
        role = await self.role_crud.get(self.db, id=id)
        if not role:
            raise NotFoundException(message="角色不存在")

        resp = RoleResponse(
            id=role.id,
            name=role.name,
            code=role.code,
            description=role.description,
            sort=role.sort,
            is_active=role.is_active,
            is_deleted=True,
            created_at=role.created_at,
            updated_at=role.updated_at,
        )

        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=[id])

        success_count, _ = await self.role_crud.batch_remove(self.db, ids=[id])
        if success_count == 0:
            raise NotFoundException(message="角色删除失败")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return resp

    @transactional()
    async def batch_delete_roles(self, ids: list[UUID], hard_delete: bool = False) -> BatchOperationResult:
        """批量删除角色。"""
        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=ids)
        success_count, failed_ids = await self.role_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._build_batch_result(success_count, failed_ids, message="删除完成")

    @transactional()
    async def restore_role(self, id: UUID) -> Role:
        """恢复已删除角色。"""
        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=[id])
        result = await self.batch_restore_roles(ids=[id])
        if result.success_count == 0:
            raise NotFoundException(message="角色不存在")

        role = await self.role_crud.get(self.db, id=id)
        if not role:
            raise NotFoundException(message="角色不存在")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return role

    @transactional()
    async def batch_restore_roles(self, ids: list[UUID]) -> BatchOperationResult:
        """批量恢复角色。"""
        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=ids)
        success_count, failed_ids = await self.role_crud.batch_restore(self.db, ids=ids)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._build_batch_result(success_count, failed_ids, message="恢复完成")
