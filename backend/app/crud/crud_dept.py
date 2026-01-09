"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_dept.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.crud.base import CRUDBase
from app.models.dept import Department
from app.schemas.dept import DeptCreate, DeptUpdate


class CRUDDept(CRUDBase[Department, DeptCreate, DeptUpdate]):
    """部门 CRUD 操作类。"""

    async def count_deleted(self, db: AsyncSession) -> int:
        """统计已删除部门数。"""

        result = await db.execute(select(func.count(Department.id)).where(Department.is_deleted.is_(True)))
        return result.scalar_one()

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

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        conditions: list[ColumnElement[bool]] = [Department.is_deleted.is_(True)]

        if keyword:
            kw = self._normalize_keyword(keyword)
            conditions.append(or_(Department.name.ilike(kw), Department.code.ilike(kw), Department.leader.ilike(kw)))

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
        conditions = []

        if not include_deleted:
            conditions.append(Department.is_deleted == False)  # noqa: E712

        if keyword:
            kw = self._normalize_keyword(keyword)
            conditions.append(or_(Department.name.ilike(kw), Department.code.ilike(kw), Department.leader.ilike(kw)))

        if is_active is not None:
            conditions.append(Department.is_active == is_active)

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
            conditions.append(or_(Department.name.ilike(kw), Department.code.ilike(kw), Department.leader.ilike(kw)))

        stmt = select(Department).where(and_(*conditions)).order_by(Department.sort.asc(), Department.created_at.desc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_children_ids(self, db: AsyncSession, *, dept_id: UUID) -> list[UUID]:
        """
        使用 PostgreSQL CTE 递归查询获取所有子部门 ID，避免 N+1 查询问题。

        Args:
            db: 数据库会话
            dept_id: 父部门 ID

        Returns:
            所有子部门 ID 列表
        """
        # 使用 CTE 递归查询，一次性获取所有子部门
        cte_sql = text("""
            WITH RECURSIVE dept_tree AS (
                -- 锚定成员：直接子部门
                SELECT id FROM department
                WHERE parent_id = :parent_id AND is_deleted = false

                UNION ALL

                -- 递归成员：子部门的子部门
                SELECT d.id FROM department d
                INNER JOIN dept_tree dt ON d.parent_id = dt.id
                WHERE d.is_deleted = false
            )
            SELECT id FROM dept_tree
        """)
        result = await db.execute(cte_sql, {"parent_id": str(dept_id)})
        return [UUID(row[0]) for row in result.fetchall()]

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
            Department.is_deleted == False,  # noqa: E712
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
                    Department.is_deleted == False,  # noqa: E712
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
                    User.is_deleted == False,  # noqa: E712
                )
            )
        )
        count = (await db.execute(stmt)).scalar() or 0
        return count > 0


dept_crud = CRUDDept(Department)
