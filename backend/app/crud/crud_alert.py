"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_alert.py
@DateTime: 2026-01-10 03:20:00
@Docs: 告警 CRUD 操作。
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertUpdate


class CRUDAlert(CRUDBase[Alert, AlertCreate, AlertUpdate]):
    """告警 CRUD 操作类。"""

    async def get(self, db: AsyncSession, id: UUID) -> Alert | None:
        """通过 ID 获取告警（预加载关联设备/发现记录）。"""
        query = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        alert_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        related_device_id: UUID | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[Alert], int]:
        """分页查询告警列表，支持筛选。"""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]

        if alert_type:
            conditions.append(self.model.alert_type == alert_type)
        if severity:
            conditions.append(self.model.severity == severity)
        if status:
            conditions.append(self.model.status == status)
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)

        keyword = self._normalize_keyword(keyword)
        if keyword:
            conditions.append(
                or_(
                    self.model.title.ilike(f"%{keyword}%"),
                    self.model.message.ilike(f"%{keyword}%"),
                )
            )

        if start_time:
            conditions.append(self.model.created_at >= start_time)
        if end_time:
            conditions.append(self.model.created_at <= end_time)

        base_query = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(and_(*conditions))
        )

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        skip = (page - 1) * page_size
        query = base_query.order_by(self.model.created_at.desc()).offset(skip).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def exists_recent_open_alert(
        self,
        db: AsyncSession,
        *,
        alert_type: str,
        related_device_id: UUID | None = None,
        related_discovery_id: UUID | None = None,
        within_minutes: int = 24 * 60,
    ) -> bool:
        """去重：是否存在最近一段时间内的未关闭告警。"""
        since = datetime.now() - timedelta(minutes=within_minutes)
        conditions = [
            self.model.is_deleted.is_(False),
            self.model.alert_type == alert_type,
            self.model.created_at >= since,
            self.model.status != "closed",
        ]
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)
        if related_discovery_id:
            conditions.append(self.model.related_discovery_id == related_discovery_id)

        query = select(func.count()).select_from(self.model).where(and_(*conditions))
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_latest_open_alert(
        self,
        db: AsyncSession,
        *,
        alert_type: str,
        related_device_id: UUID | None = None,
        related_discovery_id: UUID | None = None,
    ) -> Alert | None:
        """获取最新一条未关闭的告警（用于去重返回）。"""
        conditions = [
            self.model.is_deleted.is_(False),
            self.model.alert_type == alert_type,
            self.model.status != "closed",
        ]
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)
        if related_discovery_id:
            conditions.append(self.model.related_discovery_id == related_discovery_id)

        query = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(and_(*conditions))
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalars().first()


alert_crud = CRUDAlert(Alert)
