"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_role.py
@DateTime: 2025-12-30 14:10:00
@Docs: 角色 CRUD 操作 (Role CRUD).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.rbac import Menu, Role, UserRole
from app.schemas.role import RoleCreate, RoleUpdate


class CRUDRole(CRUDBase[Role, RoleCreate, RoleUpdate]):
    @staticmethod
    def _apply_keyword_filter(stmt, *, keyword: str | None):
        kw = CRUDBase._normalize_keyword(keyword)
        if not kw:
            return stmt

        clauses = []

        # 文本字段：角色名称、角色标识
        pattern = f"%{kw}%"
        clauses.append(or_(Role.name.ilike(pattern), Role.code.ilike(pattern)))

        # 状态（启用/禁用）
        active_true = {"启用", "正常", "有效", "active", "enabled", "true", "是", "1"}
        active_false = {"禁用", "停用", "无效", "inactive", "disabled", "false", "否", "0"}
        if kw.lower() in active_true or kw in active_true:
            clauses.append(Role.is_active.is_(True))
        elif kw.lower() in active_false or kw in active_false:
            clauses.append(Role.is_active.is_(False))

        return stmt.where(or_(*clauses))

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Role], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        count_stmt = select(func.count(Role.id)).where(Role.is_deleted.is_(False))
        if is_active is not None:
            count_stmt = count_stmt.where(Role.is_active.is_(is_active))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(Role).options(selectinload(Role.menus)).where(Role.is_deleted.is_(False))
        if is_active is not None:
            stmt = stmt.where(Role.is_active.is_(is_active))
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(Role.sort.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_user_ids_by_role(self, db: AsyncSession, *, role_id: UUID) -> list[UUID]:
        result = await db.execute(select(UserRole.user_id).where(UserRole.role_id == role_id))
        return list(result.scalars().all())

    async def get_user_ids_by_roles(self, db: AsyncSession, *, role_ids: list[UUID]) -> list[UUID]:
        if not role_ids:
            return []
        result = await db.execute(select(UserRole.user_id).where(UserRole.role_id.in_(role_ids)))
        return list(set(result.scalars().all()))

    async def get(self, db: AsyncSession, id: UUID) -> Role | None:
        """
        通过 ID 获取角色 (包含菜单关联，避免 N+1 问题)。
        """
        result = await db.execute(
            select(Role).options(selectinload(Role.menus)).where(Role.id == id, Role.is_deleted.is_(False))
        )
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[Role]:
        """
        获取多个角色 (包含菜单关联，避免 N+1 问题)。
        """
        result = await db.execute(
            select(Role).options(selectinload(Role.menus)).where(Role.is_deleted.is_(False)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_code(self, db: AsyncSession, *, code: str) -> Role | None:
        """
        根据角色编码查询角色 (排除已软删除)。
        """
        result = await db.execute(
            select(Role).options(selectinload(Role.menus)).where(Role.code == code, Role.is_deleted.is_(False))
        )
        return result.scalars().first()

    async def get_multi_by_ids(self, db: AsyncSession, *, ids: list[UUID]) -> list[Role]:
        if not ids:
            return []
        result = await db.execute(
            select(Role).where(Role.id.in_(ids), Role.is_deleted.is_(False)).order_by(Role.sort.asc())
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: RoleCreate) -> Role:
        db_obj = Role(name=obj_in.name, code=obj_in.code, description=obj_in.description, sort=obj_in.sort)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: Role, obj_in: RoleUpdate | dict[str, Any]) -> Role:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "menu_ids" in update_data:
            menu_ids = update_data.pop("menu_ids")
            if menu_ids is not None:
                result = await db.execute(select(Menu).where(Menu.id.in_(menu_ids), Menu.is_deleted.is_(False)))
                menus = list(result.scalars().all())
                db_obj.menus = menus

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def count_deleted(self, db: AsyncSession) -> int:
        """
        统计已删除角色数。
        """
        result = await db.execute(select(func.count(Role.id)).where(Role.is_deleted.is_(True)))
        return result.scalar_one()

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Role], int]:
        """
        获取已删除角色列表 (分页)。
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        count_stmt = select(func.count(Role.id)).where(Role.is_deleted.is_(True))
        if is_active is not None:
            count_stmt = count_stmt.where(Role.is_active.is_(is_active))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(Role).options(selectinload(Role.menus)).where(Role.is_deleted.is_(True))
        if is_active is not None:
            stmt = stmt.where(Role.is_active.is_(is_active))
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(Role.sort.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total


role = CRUDRole(Role)
