"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_credential.py
@DateTime: 2026-01-09 19:15:00
@Docs: 设备分组凭据 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.crud.base import CRUDBase
from app.models.credential import DeviceGroupCredential
from app.schemas.credential import DeviceGroupCredentialCreate, DeviceGroupCredentialUpdate


class CRUDCredential(CRUDBase[DeviceGroupCredential, DeviceGroupCredentialCreate, DeviceGroupCredentialUpdate]):
    """设备分组凭据 CRUD 操作类。"""

    async def get(self, db: AsyncSession, id: UUID) -> DeviceGroupCredential | None:
        """
        通过 ID 获取凭据（预加载部门关联）。
        """
        query = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_dept_and_group(
        self, db: AsyncSession, dept_id: UUID, device_group: str
    ) -> DeviceGroupCredential | None:
        """
        通过部门ID和设备分组获取凭据。

        Args:
            db: 数据库会话
            dept_id: 部门ID
            device_group: 设备分组

        Returns:
            DeviceGroupCredential | None: 凭据对象或 None
        """
        query = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(self.model.dept_id == dept_id)
            .where(self.model.device_group == device_group)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def exists_credential(
        self,
        db: AsyncSession,
        dept_id: UUID,
        device_group: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        检查凭据是否已存在。

        Args:
            db: 数据库会话
            dept_id: 部门ID
            device_group: 设备分组
            exclude_id: 排除的凭据ID（用于更新时排除自身）

        Returns:
            bool: 凭据是否已存在
        """
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.dept_id == dept_id)
            .where(self.model.device_group == device_group)
            .where(self.model.is_deleted.is_(False))
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        dept_id: UUID | None = None,
        device_group: str | None = None,
    ) -> tuple[list[DeviceGroupCredential], int]:
        """
        获取分页过滤的凭据列表。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            dept_id: 部门筛选
            device_group: 设备分组筛选

        Returns:
            (items, total): 凭据列表和总数
        """
        page, page_size = self._validate_pagination(page, page_size)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]
        if dept_id:
            conditions.append(self.model.dept_id == dept_id)
        if device_group:
            conditions.append(self.model.device_group == device_group)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(DeviceGroupCredential.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500)

    async def get_by_dept(self, db: AsyncSession, dept_id: UUID) -> list[DeviceGroupCredential]:
        """
        获取指定部门的所有凭据。

        Args:
            db: 数据库会话
            dept_id: 部门ID

        Returns:
            list[DeviceGroupCredential]: 凭据列表
        """
        query = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(self.model.dept_id == dept_id)
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.device_group)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[DeviceGroupCredential], int]:
        """
        获取已删除凭据的分页列表（回收站）。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 关键字搜索

        Returns:
            (items, total): 已删除凭据列表和总数
        """
        page, page_size = self._validate_pagination(page, page_size)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(True)]
        keyword_clause = self._or_ilike_contains(keyword, [self.model.username, self.model.description])
        if keyword_clause is not None:
            conditions.append(keyword_clause)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(DeviceGroupCredential.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(where_clause)
            .order_by(self.model.updated_at.desc())
        )
        return await self.paginate(db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500)

    async def get_deleted(self, db: AsyncSession, id: UUID) -> DeviceGroupCredential | None:
        """
        获取已删除的凭据（用于恢复或彻底删除）。

        Args:
            db: 数据库会话
            id: 凭据ID

        Returns:
            DeviceGroupCredential | None: 凭据对象或 None
        """
        query = (
            select(self.model)
            .options(selectinload(DeviceGroupCredential.dept))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(True))
        )
        result = await db.execute(query)
        return result.scalars().first()


# 单例实例
credential = CRUDCredential(DeviceGroupCredential)
