"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: role_service.py
@DateTime: 2025-12-30 14:50:00
@Docs: 角色服务业务逻辑 (Role Service Logic).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_user_permissions_cache
from app.core.decorator import transactional
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_menu import CRUDMenu
from app.crud.crud_role import CRUDRole
from app.models.rbac import Role
from app.schemas.role import RoleCreate, RoleResponse, RoleUpdate


class RoleService:
    """
    角色服务类。
    """

    def __init__(self, db: AsyncSession, role_crud: CRUDRole, menu_crud: CRUDMenu):
        self.db = db
        self.role_crud = role_crud
        self.menu_crud = menu_crud

        # transactional() 将在 commit 后执行这些任务（用于缓存失效等）
        self._post_commit_tasks: list = []

    def _invalidate_permissions_cache_after_commit(self, user_ids: list[UUID]) -> None:
        async def _task() -> None:
            await invalidate_user_permissions_cache(user_ids)

        self._post_commit_tasks.append(_task)

    async def get_roles(self, skip: int = 0, limit: int = 100) -> list[Role]:
        return await self.role_crud.get_multi(self.db, skip=skip, limit=limit)

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

        affected_user_ids = await self.role_crud.get_user_ids_by_role(self.db, role_id=role_id)

        unique_menu_ids = list(dict.fromkeys(menu_ids))
        menus = await self.menu_crud.get_multi_by_ids(self.db, ids=unique_menu_ids)
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

        affected_user_ids = await self.role_crud.get_user_ids_by_role(self.db, role_id=id)

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

        affected_user_ids = await self.role_crud.get_user_ids_by_role(self.db, role_id=id)

        deleted_role = await self.role_crud.remove(self.db, id=id)
        if not deleted_role:
            raise NotFoundException(message="角色删除失败")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)

        return RoleResponse(
            id=deleted_role.id,
            name=deleted_role.name,
            code=deleted_role.code,
            description=deleted_role.description,
            sort=deleted_role.sort,
            is_active=deleted_role.is_active,
            is_deleted=deleted_role.is_deleted,
            created_at=deleted_role.created_at,
            updated_at=deleted_role.updated_at,
        )

    @transactional()
    async def batch_delete_roles(self, ids: list[UUID], hard_delete: bool = False) -> tuple[int, list[UUID]]:
        """
        批量删除角色。
        """
        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=ids)
        result = await self.role_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return result

    @transactional()
    async def restore_role(self, id: UUID) -> Role:
        """
        恢复已删除角色。
        """
        affected_user_ids = await self.role_crud.get_user_ids_by_role(self.db, role_id=id)
        role = await self.role_crud.restore(self.db, id=id)
        if not role:
            raise NotFoundException(message="角色不存在")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return role

    @transactional()
    async def batch_restore_roles(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """批量恢复角色。"""

        success_count = 0
        failed_ids: list[UUID] = []

        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return success_count, failed_ids

        affected_user_ids = await self.role_crud.get_user_ids_by_roles(self.db, role_ids=unique_ids)

        for role_id in unique_ids:
            role = await self.role_crud.restore(self.db, id=role_id)
            if not role:
                failed_ids.append(role_id)
                continue
            success_count += 1

        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return success_count, failed_ids
