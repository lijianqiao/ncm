"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alerts.py
@DateTime: 2026-01-10 04:20:00
@Docs: 告警 Celery 任务 (Alert Tasks).

包含离线设备与影子资产的定时告警扫描。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.enums import AlertSeverity, AlertType, DiscoveryStatus
from app.core.logger import logger
from app.crud.crud_alert import alert_crud
from app.models.discovery import Discovery
from app.schemas.alert import AlertCreate
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.alerts.scheduled_offline_alerts",
    queue="discovery",
)
def scheduled_offline_alerts(self) -> dict[str, Any]:
    """
    定时扫描离线设备与影子资产，并生成告警。

    - 离线阈值：settings.ALERT_OFFLINE_DAYS_THRESHOLD（默认 3 天）
    - 影子资产：Discovery.status == SHADOW
    """

    task_id = self.request.id
    started_at = datetime.now(UTC)

    async def _scan() -> dict[str, Any]:
        created_offline = 0
        created_shadow = 0

        async with AsyncSessionLocal() as db:
            service = AlertService(db, alert_crud)
            notifier = NotificationService()

            # 1) 离线设备：offline_days >= threshold
            offline_query = (
                select(Discovery)
                .where(Discovery.is_deleted.is_(False))
                .where(Discovery.offline_days >= settings.ALERT_OFFLINE_DAYS_THRESHOLD)
                .order_by(Discovery.offline_days.desc())
            )
            offline_rs = await db.execute(offline_query)
            offline_items = list(offline_rs.scalars().all())

            for d in offline_items:
                title = f"设备离线: {d.ip_address}"
                alert = await service.create_alert(
                    AlertCreate(
                        alert_type=AlertType.DEVICE_OFFLINE,
                        severity=AlertSeverity.HIGH,
                        title=title,
                        message=f"设备已离线 {d.offline_days} 天",
                        details={
                            "ip_address": d.ip_address,
                            "mac_address": d.mac_address,
                            "offline_days": d.offline_days,
                            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                            "matched_device_id": str(d.matched_device_id) if d.matched_device_id else None,
                        },
                        source="discovery",
                        related_device_id=d.matched_device_id,
                        related_discovery_id=d.id,
                    ),
                    dedup_minutes=24 * 60,
                )
                await notifier.send_webhook(alert)
                created_offline += 1

            # 2) 影子资产：status == SHADOW
            shadow_query = (
                select(Discovery)
                .where(Discovery.is_deleted.is_(False))
                .where(Discovery.status == DiscoveryStatus.SHADOW.value)
                .order_by(Discovery.created_at.desc())
            )
            shadow_rs = await db.execute(shadow_query)
            shadow_items = list(shadow_rs.scalars().all())

            for d in shadow_items:
                title = f"影子资产: {d.ip_address}"
                alert = await service.create_alert(
                    AlertCreate(
                        alert_type=AlertType.SHADOW_ASSET,
                        severity=AlertSeverity.MEDIUM,
                        title=title,
                        message="发现未纳管设备（影子资产）",
                        details={
                            "ip_address": d.ip_address,
                            "mac_address": d.mac_address,
                            "vendor": d.vendor,
                            "hostname": d.hostname,
                            "open_ports": d.open_ports,
                            "first_seen_at": d.first_seen_at.isoformat() if d.first_seen_at else None,
                            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                        },
                        source="discovery",
                        related_discovery_id=d.id,
                    ),
                    dedup_minutes=24 * 60,
                )
                await notifier.send_webhook(alert)
                created_shadow += 1

        return {
            "task_id": task_id,
            "created_offline": created_offline,
            "created_shadow": created_shadow,
        }

    try:
        result = run_async(_scan())
        ended_at = datetime.now(UTC)
        logger.info(
            "告警扫描完成",
            task_id=task_id,
            created_offline=result.get("created_offline", 0),
            created_shadow=result.get("created_shadow", 0),
            duration_seconds=(ended_at - started_at).total_seconds(),
        )
        return result
    except Exception as e:
        logger.error("告警扫描失败", task_id=task_id, error=str(e), exc_info=True)
        raise
