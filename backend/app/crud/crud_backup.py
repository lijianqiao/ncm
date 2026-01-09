"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_backup.py
@DateTime: 2026-01-09 20:05:00
@Docs: 配置备份 CRUD 操作。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.backup import Backup
from app.schemas.backup import BackupCreate


class BackupUpdate(BackupCreate):
    """备份更新模型（内部使用）。"""

    pass


class CRUDBackup(CRUDBase[Backup, BackupCreate, BackupUpdate]):
    """配置备份 CRUD 操作类。"""

    async def get(self, db: AsyncSession, id: UUID) -> Backup | None:
        """
        通过 ID 获取备份（预加载设备关联）。
        """
        query = (
            select(self.model)
            .options(selectinload(Backup.device), selectinload(Backup.operator))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_device(
        self,
        db: AsyncSession,
        device_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Backup], int]:
        """
        获取指定设备的备份历史（分页）。

        Args:
            db: 数据库会话
            device_id: 设备ID
            page: 页码
            page_size: 每页数量

        Returns:
            (items, total): 备份列表和总数
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 基础查询
        base_query = select(self.model).where(self.model.device_id == device_id).where(self.model.is_deleted.is_(False))

        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询（按创建时间倒序）
        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(Backup.device), selectinload(Backup.operator))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

    async def get_latest_by_device(self, db: AsyncSession, device_id: UUID) -> Backup | None:
        """
        获取设备的最新备份。

        Args:
            db: 数据库会话
            device_id: 设备ID

        Returns:
            Backup | None: 最新备份或 None
        """
        query = (
            select(self.model)
            .options(selectinload(Backup.device))
            .where(self.model.device_id == device_id)
            .where(self.model.is_deleted.is_(False))
            .where(self.model.status == "success")  # 只获取成功的备份
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_latest_md5_by_device(self, db: AsyncSession, device_id: UUID) -> str | None:
        """
        获取设备最新成功备份的 MD5 哈希值。

        用于增量备份检测配置变更。

        Args:
            db: 数据库会话
            device_id: 设备ID

        Returns:
            str | None: MD5 哈希值或 None
        """
        query = (
            select(self.model.md5_hash)
            .where(self.model.device_id == device_id)
            .where(self.model.is_deleted.is_(False))
            .where(self.model.status == "success")
            .where(self.model.md5_hash.isnot(None))
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar()

    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        device_id: UUID | None = None,
        backup_type: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[Backup], int]:
        """
        获取分页过滤的备份列表。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            device_id: 设备ID筛选
            backup_type: 备份类型筛选
            status: 状态筛选
            start_date: 开始时间筛选
            end_date: 结束时间筛选

        Returns:
            (items, total): 备份列表和总数
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 基础查询
        base_query = select(self.model).where(self.model.is_deleted.is_(False))

        # 设备筛选
        if device_id:
            base_query = base_query.where(self.model.device_id == device_id)

        # 备份类型筛选
        if backup_type:
            base_query = base_query.where(self.model.backup_type == backup_type)

        # 状态筛选
        if status:
            base_query = base_query.where(self.model.status == status)

        # 时间范围筛选
        if start_date:
            base_query = base_query.where(self.model.created_at >= start_date)
        if end_date:
            base_query = base_query.where(self.model.created_at <= end_date)

        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(Backup.device), selectinload(Backup.operator))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

    async def count_by_device(self, db: AsyncSession, device_id: UUID) -> int:
        """
        获取设备的备份数量。

        Args:
            db: 数据库会话
            device_id: 设备ID

        Returns:
            int: 备份数量
        """
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.device_id == device_id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalar() or 0

    async def get_devices_latest_md5(self, db: AsyncSession, device_ids: list[UUID]) -> dict[UUID, str]:
        """
        批量获取多个设备的最新 MD5 哈希值。

        Args:
            db: 数据库会话
            device_ids: 设备ID列表

        Returns:
            dict[UUID, str]: 设备ID -> MD5 的映射
        """
        if not device_ids:
            return {}

        # 使用窗口函数获取每个设备的最新备份
        from sqlalchemy.sql import func as sql_func

        # 子查询：为每个设备的备份按时间排序
        subquery = (
            select(
                self.model.device_id,
                self.model.md5_hash,
                sql_func.row_number()
                .over(partition_by=self.model.device_id, order_by=self.model.created_at.desc())
                .label("rn"),
            )
            .where(self.model.device_id.in_(device_ids))
            .where(self.model.is_deleted.is_(False))
            .where(self.model.status == "success")
            .where(self.model.md5_hash.isnot(None))
            .subquery()
        )

        # 主查询：只取每个设备的最新记录
        query = select(subquery.c.device_id, subquery.c.md5_hash).where(subquery.c.rn == 1)

        result = await db.execute(query)
        return {row.device_id: row.md5_hash for row in result.fetchall()}


# 单例实例
backup = CRUDBackup(Backup)
