"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_alert.py
@DateTime: 2026-01-10 03:20:00
@Docs: 告警 CRUD 操作。
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import AlertStatus
from app.crud.base import CRUDBase
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertUpdate


class CRUDAlert(CRUDBase[Alert, AlertCreate, AlertUpdate]):
    """告警 CRUD 操作类。"""

    # 告警关联加载选项
    _ALERT_OPTIONS = [selectinload(Alert.related_device), selectinload(Alert.related_discovery)]

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> Alert | None:
        """通过 ID 获取告警（预加载关联设备/发现记录）。"""
        return await super().get(db, id, is_deleted=is_deleted, options=options or self._ALERT_OPTIONS)

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
            self.model.status.in_(AlertStatus.open_statuses()),
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
            self.model.status.in_(AlertStatus.open_statuses()),
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
