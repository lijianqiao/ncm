"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: menu_service.py
@DateTime: 2025-12-30 14:55:00
@Docs: 菜单服务业务逻辑 (Menu Service Logic).
"""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import MenuType
from app.core.exceptions import DomainValidationException, NotFoundException
from app.core.permissions import PermissionCode
from app.crud.crud_menu import CRUDMenu
from app.models.rbac import Menu
from app.models.user import User
from app.schemas.common import BatchOperationResult
from app.schemas.menu import MenuCreate, MenuResponse, MenuUpdate
from app.services.base import BaseService, PermissionCacheMixin


class MenuService(BaseService, PermissionCacheMixin):
    """
    菜单服务类。
    """

    def __init__(self, db: AsyncSession, menu_crud: CRUDMenu):
        super().__init__(db)
        self.menu_crud = menu_crud

    @staticmethod
    def _to_menu_response(menu: Menu, *, children: list[MenuResponse] | None = None) -> MenuResponse:
        """将 ORM Menu 转为响应对象，避免访问关系属性触发隐式 IO。"""

        return MenuResponse(
            id=menu.id,
            title=menu.title,
            name=menu.name,
            type=MenuType(menu.type),
            parent_id=menu.parent_id,
            path=menu.path,
            component=menu.component,
            icon=menu.icon,
            sort=menu.sort,
            is_hidden=menu.is_hidden,
            permission=menu.permission,
            is_deleted=menu.is_deleted,
            is_active=menu.is_active,
            created_at=menu.created_at,
            updated_at=menu.updated_at,
            children=children,
        )

    @staticmethod
    def _normalize_path(path: str | None) -> str | None:
        if path is None:
            return None
        p = path.strip()
        return p or None

    @staticmethod
    def _is_permission_code_registered(code: str) -> bool:
        return code in {c.value for c in PermissionCode}

    async def _validate_menu_fields(
        self, *, menu_type: MenuType, path: str | None, permission: str | None, menu_id=None
    ) -> None:
        """按 MenuType 校验字段组合，尽量在写库前拦截无效数据。"""

        normalized_path = self._normalize_path(path)

        # 允许的 path 形式：/system/users、/a-b/c_d 等（不允许空格）
        if normalized_path is not None and not re.fullmatch(r"/[A-Za-z0-9/_\-]*", normalized_path):
            raise DomainValidationException(message="path 格式不正确，示例：/system/users")

        if menu_type == MenuType.CATALOG:
            if normalized_path is not None:
                raise DomainValidationException(message="CATALOG 类型不允许填写 path")
            # 目录一般不绑定权限码；如确实需要，可后续再放开
            if permission is not None:
                raise DomainValidationException(message="CATALOG 类型不允许填写 permission")
            return

        if menu_type == MenuType.MENU:
            # 兼容历史数据：MENU 的 path 允许为空；如果填写则要求格式正确且唯一
            if normalized_path is not None:
                if await self.menu_crud.exists_path(self.db, path=normalized_path, exclude_id=menu_id):
                    raise DomainValidationException(message="path 已存在，请更换")
            if permission is not None and not self._is_permission_code_registered(permission):
                raise DomainValidationException(message="permission 未注册，请从权限字典选择")
            return

        if menu_type == MenuType.PERMISSION:
            if normalized_path is not None:
                raise DomainValidationException(message="PERMISSION 类型不允许填写 path")
            if not permission:
                raise DomainValidationException(message="PERMISSION 类型必须填写 permission")
            if not self._is_permission_code_registered(permission):
                raise DomainValidationException(message="permission 未注册，请从权限字典选择")
            return

    async def get_menus(self) -> list[Menu]:
        # 使用分页查询替代 get_multi
        menus, _ = await self.menu_crud.get_multi_paginated(self.db, page=1, page_size=100)
        return menus

    async def get_menu(self, menu_id: UUID) -> MenuResponse:
        """获取单个菜单详情。"""
        menu = await self.menu_crud.get(self.db, id=menu_id)
        if not menu:
            raise NotFoundException(message="菜单不存在")
        return self._to_menu_response(menu, children=[])

    async def get_menu_options_tree(self) -> list[MenuResponse]:
        """获取可分配菜单 options 树（用于角色创建/编辑时选择菜单）。"""

        menus = await self.menu_crud.get_all_not_deleted(self.db)
        if not menus:
            return []

        id_to_node: dict[UUID, MenuResponse] = {}
        for m in menus:
            id_to_node[m.id] = MenuResponse(
                id=m.id,
                title=m.title,
                name=m.name,
                type=MenuType(m.type),
                parent_id=m.parent_id,
                path=m.path,
                component=m.component,
                icon=m.icon,
                sort=m.sort,
                is_hidden=m.is_hidden,
                permission=m.permission,
                is_deleted=m.is_deleted,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
                children=[],
            )

        roots: list[MenuResponse] = []
        for m in menus:
            node = id_to_node[m.id]
            if m.parent_id and m.parent_id in id_to_node:
                id_to_node[m.parent_id].children = (id_to_node[m.parent_id].children or []) + [node]
            else:
                roots.append(node)

        # 按 sort 对每层 children 排序
        def _sort_recursive(items: list[MenuResponse]) -> None:
            items.sort(key=lambda x: x.sort)
            for it in items:
                if it.children:
                    _sort_recursive(it.children)

        _sort_recursive(roots)
        return roots

    async def get_my_menus_tree(self, current_user: User) -> list[MenuResponse]:
        """获取当前用户可见的导航菜单树（不返回隐藏权限点）。"""

        menus = await self.menu_crud.get_all_not_deleted(self.db)
        if not menus:
            return []

        if current_user.is_superuser:
            allowed_permissions: set[str] = {"*"}
        else:
            allowed_permissions = set()
            for role in current_user.roles:
                for menu in role.menus:
                    if menu.permission:
                        allowed_permissions.add(menu.permission)

        # id_to_menu: dict[UUID, Menu] = {m.id: m for m in menus}
        parent_to_children: dict[UUID | None, list[Menu]] = {}
        for m in menus:
            parent_to_children.setdefault(m.parent_id, []).append(m)
        for children in parent_to_children.values():
            children.sort(key=lambda x: x.sort)

        def _is_allowed_by_permission(menu: Menu) -> bool:
            # 仪表盘：所有已登录用户都可见（不依赖任何角色/权限）
            if menu.path == "/dashboard":
                return True
            if "*" in allowed_permissions:
                return True
            if menu.permission:
                return menu.permission in allowed_permissions
            return False

        def _build(menu: Menu) -> tuple[bool, MenuResponse | None]:
            children = parent_to_children.get(menu.id, [])

            any_child_allowed = False
            visible_children: list[MenuResponse] = []
            for c in children:
                child_allowed, child_node = _build(c)
                any_child_allowed = any_child_allowed or child_allowed
                if child_node is not None:
                    visible_children.append(child_node)

            self_allowed = _is_allowed_by_permission(menu)
            allowed = self_allowed or any_child_allowed

            # 不输出隐藏菜单（权限点），但它们会影响父级 allowed
            if menu.type == MenuType.PERMISSION or menu.is_hidden:
                return allowed, None

            # 对于 permission 为空的“分组/页面菜单”，仅当自己有权限或有可见子菜单时才展示
            if not allowed:
                return False, None

            node = MenuResponse(
                id=menu.id,
                title=menu.title,
                name=menu.name,
                type=MenuType(menu.type),
                parent_id=menu.parent_id,
                path=menu.path,
                component=menu.component,
                icon=menu.icon,
                sort=menu.sort,
                is_hidden=menu.is_hidden,
                permission=menu.permission,
                is_deleted=menu.is_deleted,
                is_active=menu.is_active,
                created_at=menu.created_at,
                updated_at=menu.updated_at,
                children=visible_children,
            )
            return True, node

        roots = parent_to_children.get(None, [])
        result: list[MenuResponse] = []
        for r in roots:
            allowed, node = _build(r)
            if allowed and node is not None:
                result.append(node)
        return result

    async def get_menus_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
        is_hidden: bool | None = None,
        type: MenuType | None = None,
    ) -> tuple[list[MenuResponse], int]:
        """
        获取分页菜单列表。
        """
        menus, total = await self.menu_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
            is_hidden=is_hidden,
            type=type,
        )
        return [self._to_menu_response(m, children=[]) for m in menus], total

    async def get_deleted_menus(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
        is_hidden: bool | None = None,
        type: MenuType | None = None,
    ) -> tuple[list[MenuResponse], int]:
        """
        获取已删除菜单列表 (回收站 - 分页)。
        """
        menus, total = await self.menu_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
            is_hidden=is_hidden,
            type=type,
        )
        return [self._to_menu_response(m, children=[]) for m in menus], total

    @transactional()
    async def create_menu(self, obj_in: MenuCreate) -> MenuResponse:
        await self._validate_menu_fields(menu_type=obj_in.type, path=obj_in.path, permission=obj_in.permission)
        menu = await self.menu_crud.create(self.db, obj_in=obj_in)
        self._invalidate_permissions_cache_after_commit([])
        return self._to_menu_response(menu, children=[])

    @transactional()
    async def update_menu(self, id: UUID, obj_in: MenuUpdate) -> MenuResponse:
        menu = await self.menu_crud.get(self.db, id=id)
        if not menu:
            raise NotFoundException(message="菜单不存在")

        # 用“更新后的值”做组合校验（支持部分更新）
        final_type = obj_in.type if obj_in.type else MenuType(menu.type)
        final_path = obj_in.path if obj_in.path is not None else menu.path
        final_permission = obj_in.permission if obj_in.permission is not None else menu.permission
        await self._validate_menu_fields(
            menu_type=final_type,
            path=final_path,
            permission=final_permission,
            menu_id=id,
        )

        affected_user_ids = await self.menu_crud.get_affected_user_ids(self.db, menu_id=id)
        updated = await self.menu_crud.update(self.db, db_obj=menu, obj_in=obj_in)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._to_menu_response(updated, children=[])

    @transactional()
    async def delete_menu(self, id: UUID) -> MenuResponse:
        menu = await self.menu_crud.get(self.db, id=id)
        if not menu:
            raise NotFoundException(message="菜单不存在")

        resp = MenuResponse(
            id=menu.id,
            title=menu.title,
            name=menu.name,
            sort=menu.sort,
            type=MenuType(menu.type),
            parent_id=menu.parent_id,
            path=menu.path,
            component=menu.component,
            icon=menu.icon,
            is_hidden=menu.is_hidden,
            permission=menu.permission,
            is_deleted=True,
            is_active=menu.is_active,
            created_at=menu.created_at,
            updated_at=menu.updated_at,
            children=[],
        )

        affected_user_ids = await self.menu_crud.get_affected_user_ids(self.db, menu_id=id)

        success_count, _ = await self.menu_crud.batch_remove(self.db, ids=[id])
        if success_count == 0:
            raise NotFoundException(message="菜单删除失败")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)

        # 手动构建响应，避免访问 menu.children 触发 implicit IO (MissingGreenlet)
        # 且删除后的对象 children 应为空
        return resp

    @transactional()
    async def batch_delete_menus(self, ids: list[UUID], hard_delete: bool = False) -> BatchOperationResult:
        """批量删除菜单。"""
        affected_user_ids = await self.menu_crud.get_affected_user_ids_by_menu_ids(self.db, menu_ids=ids)
        success_count, failed_ids = await self.menu_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._build_batch_result(success_count, failed_ids, message="删除完成")

    @transactional()
    async def restore_menu(self, id: UUID) -> MenuResponse:
        """恢复已删除菜单。"""
        affected_user_ids = await self.menu_crud.get_affected_user_ids(self.db, menu_id=id)
        result = await self.batch_restore_menus(ids=[id])
        if result.success_count == 0:
            raise NotFoundException(message="菜单不存在")

        menu = await self.menu_crud.get(self.db, id=id)
        if not menu:
            raise NotFoundException(message="菜单不存在")

        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._to_menu_response(menu, children=[])

    @transactional()
    async def batch_restore_menus(self, ids: list[UUID]) -> BatchOperationResult:
        """批量恢复菜单。"""
        affected_user_ids = await self.menu_crud.get_affected_user_ids_by_menu_ids(self.db, menu_ids=ids)
        success_count, failed_ids = await self.menu_crud.batch_restore(self.db, ids=ids)
        self._invalidate_permissions_cache_after_commit(affected_user_ids)
        return self._build_batch_result(success_count, failed_ids, message="恢复完成")
