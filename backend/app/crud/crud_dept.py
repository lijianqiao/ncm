"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_dept.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 CRUD 操作。
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.dept import Department
from app.schemas.dept import DeptCreate, DeptUpdate

# 关联加载选项
_CHILDREN_OPTIONS = [selectinload(Department.children)]

# 关键词搜索列
_KEYWORD_COLUMNS = [Department.name, Department.code, Department.leader]

# 默认排序
_DEFAULT_ORDER = (Department.sort.asc(), Department.created_at.desc())


class CRUDDept(CRUDBase[Department, DeptCreate, DeptUpdate]):
    """部门 CRUD 操作类。"""

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
            keyword_clause = self._or_ilike_contains(keyword, _KEYWORD_COLUMNS)
            if keyword_clause is not None:
                conditions.append(keyword_clause)

        stmt = select(Department)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(*_DEFAULT_ORDER)

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
