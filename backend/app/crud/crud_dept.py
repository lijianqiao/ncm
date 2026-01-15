"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_dept.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.crud.base import CRUDBase
from app.models.dept import Department
from app.schemas.dept import DeptCreate, DeptUpdate


class CRUDDept(CRUDBase[Department, DeptCreate, DeptUpdate]):
    """部门 CRUD 操作类。"""

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Department], int]:
        """获取已删除部门列表 (回收站 - 分页)。"""

        page, page_size = self._validate_pagination(page, page_size)

        conditions: list[ColumnElement[bool]] = [Department.is_deleted.is_(True)]

        kw = self._normalize_keyword(keyword)
        if kw:
            escaped = self._escape_like(kw)
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    Department.name.ilike(pattern, escape="\\"),
                    Department.code.ilike(pattern, escape="\\"),
                    Department.leader.ilike(pattern, escape="\\"),
                )
            )

        if is_active is not None:
            conditions.append(Department.is_active.is_(is_active))

        count_stmt = select(func.count(Department.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Department)
            .options(selectinload(Department.children))
            .where(and_(*conditions))
            .order_by(Department.sort.asc(), Department.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total)

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Department], int]:
        """
        分页查询部门列表。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 关键词（搜索名称/编码/负责人）
            is_active: 是否启用过滤
            include_deleted: 是否包含已删除

        Returns:
            部门列表和总数
        """
        page, page_size = self._validate_pagination(page, page_size)

        conditions: list[ColumnElement[bool]] = []

        if not include_deleted:
            conditions.append(Department.is_deleted.is_(False))

        kw = self._normalize_keyword(keyword)
        if kw:
            escaped = self._escape_like(kw)
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    Department.name.ilike(pattern, escape="\\"),
                    Department.code.ilike(pattern, escape="\\"),
                    Department.leader.ilike(pattern, escape="\\"),
                )
            )

        if is_active is not None:
            conditions.append(Department.is_active.is_(is_active))

        # 查询总数
        count_stmt = select(func.count()).select_from(Department)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar() or 0

        # 查询数据
        stmt = select(Department).options(selectinload(Department.children))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Department.sort.asc(), Department.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total)

    async def get_tree(
        self,
        db: AsyncSession,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
        include_deleted: bool = False,
    ) -> list[Department]:
        """
        获取部门树结构所需的部门列表（一次性加载，避免异步懒加载）。

        Args:
            db: 数据库会话
            is_active: 是否启用过滤
            include_deleted: 是否包含已删除

        Returns:
            部门列表（用于在 Service 层构建树）
        """
        conditions = []

        if not include_deleted:
            conditions.append(Department.is_deleted.is_(False))

        if is_active is not None:
            conditions.append(Department.is_active.is_(is_active))

        if keyword:
            kw = self._normalize_keyword(keyword)
            if kw:
                escaped = self._escape_like(kw)
                pattern = f"%{escaped}%"
                conditions.append(
                    or_(
                        Department.name.ilike(pattern, escape="\\"),
                        Department.code.ilike(pattern, escape="\\"),
                        Department.leader.ilike(pattern, escape="\\"),
                    )
                )

        stmt = select(Department)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Department.sort.asc(), Department.created_at.desc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_deleted(self, db: AsyncSession, *, dept_id: UUID) -> Department | None:
        """获取已软删除的部门记录。"""
        stmt = select(Department).where(Department.id == dept_id, Department.is_deleted.is_(True))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_children_ids(self, db: AsyncSession, *, dept_id: UUID) -> list[UUID]:
        """
        使用 PostgreSQL CTE 递归查询获取所有子部门 ID，避免 N+1 查询问题。

        Args:
            db: 数据库会话
            dept_id: 父部门 ID

        Returns:
            所有子部门 ID 列表
        """
        dept_tree = (
            select(Department.id)
            .where(Department.parent_id == dept_id, Department.is_deleted.is_(False))
            .cte(name="dept_tree", recursive=True)
        )
        dept_tree = dept_tree.union_all(
            select(Department.id).where(Department.parent_id == dept_tree.c.id, Department.is_deleted.is_(False))
        )

        result = await db.execute(select(dept_tree.c.id))
        ids = list(result.scalars().all())
        return [id_ if isinstance(id_, UUID) else UUID(str(id_)) for id_ in ids]

    async def exists_code(self, db: AsyncSession, *, code: str, exclude_id: UUID | None = None) -> bool:
        """
        检查部门编码是否已存在。

        Args:
            db: 数据库会话
            code: 部门编码
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            是否存在
        """

        conditions = [
            Department.code == code,
            Department.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(Department.id != exclude_id)

        stmt = select(func.count()).select_from(Department).where(and_(*conditions))
        count = (await db.execute(stmt)).scalar() or 0
        return count > 0

    async def has_children(self, db: AsyncSession, *, dept_id: UUID) -> bool:
        """
        检查部门是否有子部门。

        Args:
            db: 数据库会话
            dept_id: 部门 ID

        Returns:
            是否有子部门
        """
        stmt = (
            select(func.count())
            .select_from(Department)
            .where(
                and_(
                    Department.parent_id == dept_id,
                    Department.is_deleted.is_(False),
                )
            )
        )
        count = (await db.execute(stmt)).scalar() or 0
        return count > 0

    async def has_users(self, db: AsyncSession, *, dept_id: UUID) -> bool:
        """
        检查部门是否有关联用户。

        Args:
            db: 数据库会话
            dept_id: 部门 ID

        Returns:
            是否有关联用户
        """
        # 延迟导入避免循环依赖
        from app.models.user import User

        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                and_(
                    User.dept_id == dept_id,
                    User.is_deleted.is_(False),
                )
            )
        )
        count = (await db.execute(stmt)).scalar() or 0
        return count > 0


dept_crud = CRUDDept(Department)
dept = dept_crud
