"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert_service.py
@DateTime: 2026-01-10 03:25:00
@Docs: 告警服务业务逻辑 (Alert Service Logic).

提供告警创建、分页查询、确认(ack)、关闭(close)等能力。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import AlertStatus, AlertType
from app.core.exceptions import NotFoundException
from app.core.logger import logger
from app.crud.crud_alert import CRUDAlert
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertListQuery, AlertUpdate
from app.schemas.common import BatchOperationResult


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
        return await self.alert_crud.get_multi_paginated(
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
    async def ack_alert(self, alert_id: UUID, *, user_id: UUID | None = None) -> Alert:
        """
        确认告警。

        Args:
            alert_id: 告警 ID
            user_id: 操作人 ID

        Returns:
            更新后的告警
        """
        alert = await self.get_alert(alert_id)
        now = datetime.now()
        update_data = AlertUpdate(
            status=AlertStatus.ACK,
            acked_by_id=user_id,
            acked_at=now,
        )
        return await self.alert_crud.update(self.db, db_obj=alert, obj_in=update_data)

    @transactional()
    async def close_alert(self, alert_id: UUID, *, user_id: UUID | None = None) -> Alert:
        """
        关闭告警。

        Args:
            alert_id: 告警 ID
            user_id: 操作人 ID

        Returns:
            更新后的告警
        """
        alert = await self.get_alert(alert_id)
        now = datetime.now()
        update_data = AlertUpdate(
            status=AlertStatus.CLOSED,
            closed_by_id=user_id,
            closed_at=now,
        )
        return await self.alert_crud.update(self.db, db_obj=alert, obj_in=update_data)

    @transactional()
    async def batch_ack_alerts(self, alert_ids: list[UUID], *, user_id: UUID | None = None) -> BatchOperationResult:
        """
        批量确认告警（使用单条 SQL）。

        Args:
            alert_ids: 告警 ID 列表
            user_id: 操作人 ID

        Returns:
            BatchOperationResult: 批量操作结果
        """
        if not alert_ids:
            return BatchOperationResult(success_count=0, failed_ids=[], message="无待处理告警")

        now = datetime.now()
        stmt = (
            update(Alert)
            .where(Alert.id.in_(alert_ids))
            .where(Alert.status == AlertStatus.OPEN.value)
            .where(Alert.is_deleted.is_(False))
            .values(
                status=AlertStatus.ACK.value,
                acked_by_id=user_id,
                acked_at=now,
                updated_at=now,
            )
        )
        result = await self.db.execute(stmt)
        success_count: int = result.rowcount or 0  # type: ignore[union-attr]

        failed_count = len(alert_ids) - success_count
        if failed_count > 0:
            logger.warning(
                "批量确认告警部分失败",
                total=len(alert_ids),
                success=success_count,
                failed=failed_count,
            )

        return BatchOperationResult(
            success_count=success_count,
            failed_ids=[],  # 使用单条 SQL 无法获取失败的具体 ID
            message=f"成功确认 {success_count} 条告警",
        )

    @transactional()
    async def batch_close_alerts(self, alert_ids: list[UUID], *, user_id: UUID | None = None) -> BatchOperationResult:
        """
        批量关闭告警（使用单条 SQL）。

        允许从 OPEN 或 ACK 状态关闭。

        Args:
            alert_ids: 告警 ID 列表
            user_id: 操作人 ID

        Returns:
            BatchOperationResult: 批量操作结果
        """
        if not alert_ids:
            return BatchOperationResult(success_count=0, failed_ids=[], message="无待处理告警")

        now = datetime.now()
        stmt = (
            update(Alert)
            .where(Alert.id.in_(alert_ids))
            .where(Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACK.value]))
            .where(Alert.is_deleted.is_(False))
            .values(
                status=AlertStatus.CLOSED.value,
                closed_by_id=user_id,
                closed_at=now,
                updated_at=now,
            )
        )
        result = await self.db.execute(stmt)
        success_count: int = result.rowcount or 0  # type: ignore[union-attr]

        failed_count = len(alert_ids) - success_count
        if failed_count > 0:
            logger.warning(
                "批量关闭告警部分失败",
                total=len(alert_ids),
                success=success_count,
                failed=failed_count,
            )

        return BatchOperationResult(
            success_count=success_count,
            failed_ids=[],
            message=f"成功关闭 {success_count} 条告警",
        )

    # ===== 自动关闭告警机制 =====

    @transactional()
    async def auto_close_offline_alerts(self, device_id: UUID) -> int:
        """
        设备恢复在线时，自动关闭相关的离线告警。

        Args:
            device_id: 设备 ID

        Returns:
            关闭的告警数量
        """
        now = datetime.now()
        stmt = (
            update(Alert)
            .where(Alert.related_device_id == device_id)
            .where(Alert.alert_type == AlertType.DEVICE_OFFLINE.value)
            .where(Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACK.value]))
            .where(Alert.is_deleted.is_(False))
            .values(
                status=AlertStatus.CLOSED.value,
                closed_at=now,
                updated_at=now,
            )
        )
        result = await self.db.execute(stmt)
        closed_count: int = result.rowcount or 0  # type: ignore[union-attr]

        if closed_count > 0:
            logger.info(
                "自动关闭离线告警",
                device_id=str(device_id),
                closed_count=closed_count,
            )

        return closed_count

    @transactional()
    async def auto_close_shadow_alerts(self, discovery_id: UUID) -> int:
        """
        影子资产被纳管时，自动关闭相关告警。

        Args:
            discovery_id: 发现记录 ID

        Returns:
            关闭的告警数量
        """
        now = datetime.now()
        stmt = (
            update(Alert)
            .where(Alert.related_discovery_id == discovery_id)
            .where(Alert.alert_type == AlertType.SHADOW_ASSET.value)
            .where(Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACK.value]))
            .where(Alert.is_deleted.is_(False))
            .values(
                status=AlertStatus.CLOSED.value,
                closed_at=now,
                updated_at=now,
            )
        )
        result = await self.db.execute(stmt)
        closed_count: int = result.rowcount or 0  # type: ignore[union-attr]

        if closed_count > 0:
            logger.info(
                "自动关闭影子资产告警",
                discovery_id=str(discovery_id),
                closed_count=closed_count,
            )

        return closed_count

    # ===== 告警统计 =====

    async def get_stats(self) -> dict:
        """
        获取告警统计数据（按类型/级别/状态分组）。

        Returns:
            dict: 统计数据
        """
        return await self.alert_crud.get_stats(self.db)

    async def get_trend(self, days: int = 7) -> list[dict]:
        """
        获取告警趋势数据（近 N 天每日新增）。

        Args:
            days: 天数，默认 7 天

        Returns:
            list[dict]: 趋势数据列表
        """
        return await self.alert_crud.get_trend(self.db, days=days)
