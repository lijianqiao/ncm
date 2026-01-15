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
from sqlalchemy.sql.elements import ColumnElement

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
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        where_clause = (self.model.device_id == device_id) & (self.model.is_deleted.is_(False))
        count_stmt = select(func.count(Backup.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(Backup.device), selectinload(Backup.operator))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

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
            .options(selectinload(Backup.device), selectinload(Backup.operator))
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

    async def get_multi_paginated(
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
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]
        if device_id:
            conditions.append(self.model.device_id == device_id)
        if backup_type:
            conditions.append(self.model.backup_type == backup_type)
        if status:
            conditions.append(self.model.status == status)
        if start_date:
            conditions.append(self.model.created_at >= start_date)
        if end_date:
            conditions.append(self.model.created_at <= end_date)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(Backup.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(Backup.device), selectinload(Backup.operator))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

    async def get_multi_deleted_paginated(
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
        """获取回收站（已软删除）备份列表（分页过滤）。"""
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(True)]
        if device_id:
            conditions.append(self.model.device_id == device_id)
        if backup_type:
            conditions.append(self.model.backup_type == backup_type)
        if status:
            conditions.append(self.model.status == status)
        if start_date:
            conditions.append(self.model.created_at >= start_date)
        if end_date:
            conditions.append(self.model.created_at <= end_date)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(Backup.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(Backup.device), selectinload(Backup.operator))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

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

    async def get_devices_latest_backup_info(self, db: AsyncSession, device_ids: list[UUID]) -> dict[UUID, dict]:
        """
        批量获取多个设备的最新成功备份信息（用于差异/告警）。

        Returns:
            dict[UUID, dict]: 设备ID -> {backup_id, md5_hash, content}
        """
        if not device_ids:
            return {}

        from sqlalchemy.sql import func as sql_func

        subquery = (
            select(
                self.model.device_id,
                self.model.id.label("backup_id"),
                self.model.md5_hash,
                self.model.content,
                sql_func.row_number()
                .over(partition_by=self.model.device_id, order_by=self.model.created_at.desc())
                .label("rn"),
            )
            .where(self.model.device_id.in_(device_ids))
            .where(self.model.is_deleted.is_(False))
            .where(self.model.status == "success")
            .subquery()
        )

        query = select(subquery.c.device_id, subquery.c.backup_id, subquery.c.md5_hash, subquery.c.content).where(
            subquery.c.rn == 1
        )

        result = await db.execute(query)
        rows = result.fetchall()
        return {
            row.device_id: {"backup_id": row.backup_id, "md5_hash": row.md5_hash, "content": row.content}
            for row in rows
        }


# 单例实例
backup = CRUDBackup(Backup)
