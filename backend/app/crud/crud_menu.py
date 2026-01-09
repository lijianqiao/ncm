"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_menu.py
@DateTime: 2025-12-30 14:15:00
@Docs: 菜单 CRUD 操作 (Menu CRUD).
"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import MenuType
from app.crud.base import CRUDBase
from app.models.rbac import Menu, RoleMenu, UserRole
from app.schemas.menu import MenuCreate, MenuUpdate


class CRUDMenu(CRUDBase[Menu, MenuCreate, MenuUpdate]):
    @staticmethod
    def _children_selectinload(depth: int = 5):
        """递归预加载 children，避免序列化阶段触发懒加载导致 MissingGreenlet。"""

        if depth < 1:
            depth = 1

        loader = selectinload(Menu.children)
        current = loader
        for _ in range(depth - 1):
            current = current.selectinload(Menu.children)
        return loader

    async def get_affected_user_ids(self, db: AsyncSession, *, menu_id: UUID) -> list[UUID]:
        stmt = (
            select(UserRole.user_id)
            .join(RoleMenu, RoleMenu.role_id == UserRole.role_id)
            .where(RoleMenu.menu_id == menu_id)
        )
        result = await db.execute(stmt)
        return list(set(result.scalars().all()))

    async def get_affected_user_ids_by_menu_ids(self, db: AsyncSession, *, menu_ids: list[UUID]) -> list[UUID]:
        if not menu_ids:
            return []
        stmt = (
            select(UserRole.user_id)
            .join(RoleMenu, RoleMenu.role_id == UserRole.role_id)
            .where(RoleMenu.menu_id.in_(menu_ids))
        )
        result = await db.execute(stmt)
        return list(set(result.scalars().all()))

    async def get_tree(self, db: AsyncSession) -> list[Menu]:
        result = await db.execute(
            select(Menu)
            .options(self._children_selectinload(depth=5))
            .where(Menu.is_deleted.is_(False))
            .order_by(Menu.sort)
        )
        menus = result.scalars().all()
        return list(menus)

    async def get_options_tree(self, db: AsyncSession) -> list[Menu]:
        """获取可分配菜单树（从根节点返回，包含隐藏权限点）。"""

        result = await db.execute(
            select(Menu)
            .options(self._children_selectinload(depth=5))
            .where(Menu.is_deleted.is_(False), Menu.parent_id.is_(None))
            .order_by(Menu.sort)
        )
        return list(result.scalars().all())

    async def get_all_not_deleted(self, db: AsyncSession) -> list[Menu]:
        """获取所有未删除菜单（平铺），用于业务层自行组装树，避免递归序列化触发懒加载。"""

        result = await db.execute(select(Menu).where(Menu.is_deleted.is_(False)).order_by(Menu.sort))
        return list(result.scalars().all())

    async def get_multi_by_ids(self, db: AsyncSession, *, ids: list[UUID]) -> list[Menu]:
        if not ids:
            return []
        result = await db.execute(select(Menu).where(Menu.id.in_(ids), Menu.is_deleted.is_(False)).order_by(Menu.sort))
        return list(result.scalars().all())

    async def count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Menu.id)).where(Menu.is_deleted.is_(False)))
        return result.scalar_one()

    async def exists_path(
        self,
        db: AsyncSession,
        *,
        path: str,
        exclude_id: UUID | None = None,
        only_not_deleted: bool = True,
    ) -> bool:
        """检查 path 是否已存在（用于避免菜单路由 path 重复）。"""

        stmt = select(func.count(Menu.id)).where(Menu.path == path)
        if only_not_deleted:
            stmt = stmt.where(Menu.is_deleted.is_(False))
        if exclude_id is not None:
            stmt = stmt.where(Menu.id != exclude_id)
        return (await db.execute(stmt)).scalar_one() > 0

    @staticmethod
    def _apply_keyword_filter(stmt, *, keyword: str | None):
        kw = CRUDBase._normalize_keyword(keyword)
        if not kw:
            return stmt

        clauses = []

        # 文本字段：标题、名称、路径、权限
        pattern = f"%{kw}%"
        clauses.append(
            or_(
                Menu.title.ilike(pattern),
                Menu.name.ilike(pattern),
                Menu.path.ilike(pattern),
                Menu.permission.ilike(pattern),
            )
        )

        # 隐藏（隐藏/显示）
        hidden_true = {"隐藏", "hidden", "true", "是", "1"}
        hidden_false = {"显示", "visible", "false", "否", "0"}
        if kw.lower() in hidden_true or kw in hidden_true:
            clauses.append(Menu.is_hidden.is_(True))
        elif kw.lower() in hidden_false or kw in hidden_false:
            clauses.append(Menu.is_hidden.is_(False))

        return stmt.where(or_(*clauses))

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[Menu]:
        result = await db.execute(
            select(Menu)
            .options(self._children_selectinload(depth=5))
            .where(Menu.is_deleted.is_(False))
            .order_by(Menu.sort)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
        is_hidden: bool | None = None,
        type: MenuType | None = None,
    ) -> tuple[list[Menu], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        count_stmt = select(func.count(Menu.id)).where(Menu.is_deleted.is_(False))
        if is_active is not None:
            count_stmt = count_stmt.where(Menu.is_active.is_(is_active))
        if is_hidden is not None:
            count_stmt = count_stmt.where(Menu.is_hidden.is_(is_hidden))
        if type is not None:
            count_stmt = count_stmt.where(Menu.type == type)
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()
        stmt = (
            select(Menu)
            .options(self._children_selectinload(depth=5))
            .where(Menu.is_deleted.is_(False))
            .order_by(Menu.sort)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if is_active is not None:
            stmt = stmt.where(Menu.is_active.is_(is_active))
        if is_hidden is not None:
            stmt = stmt.where(Menu.is_hidden.is_(is_hidden))
        if type is not None:
            stmt = stmt.where(Menu.type == type)
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_deleted(self, db: AsyncSession) -> int:
        """
        统计已删除菜单数。
        """
        result = await db.execute(select(func.count(Menu.id)).where(Menu.is_deleted.is_(True)))
        return result.scalar_one()

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
        is_hidden: bool | None = None,
        type: MenuType | None = None,
    ) -> tuple[list[Menu], int]:
        """
        获取已删除菜单列表 (分页)。
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        count_stmt = select(func.count(Menu.id)).where(Menu.is_deleted.is_(True))
        if is_active is not None:
            count_stmt = count_stmt.where(Menu.is_active.is_(is_active))
        if is_hidden is not None:
            count_stmt = count_stmt.where(Menu.is_hidden.is_(is_hidden))
        if type is not None:
            count_stmt = count_stmt.where(Menu.type == type)
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()
        stmt = (
            select(Menu)
            .options(self._children_selectinload(depth=5))
            .where(Menu.is_deleted.is_(True))
            .order_by(Menu.sort)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if is_active is not None:
            stmt = stmt.where(Menu.is_active.is_(is_active))
        if is_hidden is not None:
            stmt = stmt.where(Menu.is_hidden.is_(is_hidden))
        if type is not None:
            stmt = stmt.where(Menu.type == type)
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total


menu = CRUDMenu(Menu)
