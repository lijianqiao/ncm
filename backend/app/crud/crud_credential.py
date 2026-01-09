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

    async def get_multi_paginated_filtered(
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
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 基础查询
        base_query = select(self.model).where(self.model.is_deleted.is_(False))

        # 部门筛选
        if dept_id:
            base_query = base_query.where(self.model.dept_id == dept_id)

        # 设备分组筛选
        if device_group:
            base_query = base_query.where(self.model.device_group == device_group)

        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(DeviceGroupCredential.dept))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

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


# 单例实例
credential = CRUDCredential(DeviceGroupCredential)
