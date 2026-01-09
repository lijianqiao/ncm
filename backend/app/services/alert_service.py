"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert_service.py
@DateTime: 2026-01-10 03:25:00
@Docs: 告警服务业务逻辑 (Alert Service Logic).

提供告警创建、分页查询、确认(ack)、关闭(close)等能力。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import AlertStatus
from app.core.exceptions import NotFoundException
from app.crud.crud_alert import CRUDAlert
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertListQuery, AlertUpdate


class AlertService:
    """告警服务类。"""

    def __init__(self, db: AsyncSession, alert_crud: CRUDAlert):
        self.db = db
        self.alert_crud = alert_crud

    async def get_alert(self, alert_id: UUID) -> Alert:
        alert = await self.alert_crud.get(self.db, id=alert_id)
        if not alert:
            raise NotFoundException(message="告警不存在")
        return alert

    async def list_alerts(self, query: AlertListQuery) -> tuple[list[Alert], int]:
        return await self.alert_crud.get_multi_paginated_filtered(
            self.db,
            page=query.page,
            page_size=query.page_size,
            keyword=query.keyword,
            alert_type=query.alert_type.value if query.alert_type else None,
            severity=query.severity.value if query.severity else None,
            status=query.status.value if query.status else None,
            related_device_id=query.related_device_id,
            start_time=query.start_time,
            end_time=query.end_time,
        )

    @transactional()
    async def create_alert(self, alert_in: AlertCreate, *, dedup_minutes: int = 24 * 60) -> Alert:
        # 去重：避免每天重复产生同类型同对象的告警
        exists = await self.alert_crud.exists_recent_open_alert(
            self.db,
            alert_type=alert_in.alert_type.value,
            related_device_id=alert_in.related_device_id,
            related_discovery_id=alert_in.related_discovery_id,
            within_minutes=dedup_minutes,
        )
        if exists:
            latest = await self.alert_crud.get_latest_open_alert(
                self.db,
                alert_type=alert_in.alert_type.value,
                related_device_id=alert_in.related_device_id,
                related_discovery_id=alert_in.related_discovery_id,
            )
            if latest:
                return latest

        return await self.alert_crud.create(self.db, obj_in=alert_in)

    @transactional()
    async def ack_alert(self, alert_id: UUID) -> Alert:
        alert = await self.get_alert(alert_id)
        update = AlertUpdate(status=AlertStatus.ACK)
        return await self.alert_crud.update(self.db, db_obj=alert, obj_in=update)

    @transactional()
    async def close_alert(self, alert_id: UUID) -> Alert:
        alert = await self.get_alert(alert_id)
        update = AlertUpdate(status=AlertStatus.CLOSED)
        return await self.alert_crud.update(self.db, db_obj=alert, obj_in=update)

