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
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.enums import AlertSeverity, AlertType, DiscoveryStatus
from app.core.logger import celery_task_logger
from app.crud.crud_alert import alert_crud
from app.models.discovery import Discovery
from app.schemas.alert import AlertCreate
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService

# 批处理大小，使用配置项或默认值
BATCH_SIZE = getattr(settings, "CELERY_BATCH_SIZE", 100)


async def _process_offline_devices(
    db: AsyncSession,
    service: AlertService,
    notifier: NotificationService,
) -> int:
    """
    分批处理离线设备，使用游标分页避免 offset 性能问题。

    Args:
        db: 数据库会话
        service: 告警服务
        notifier: 通知服务

    Returns:
        创建的告警数量
    """
    created = 0
    last_id: UUID | None = None

    while True:
        query = (
            select(Discovery)
            .where(Discovery.is_deleted.is_(False))
            .where(Discovery.offline_days >= settings.ALERT_OFFLINE_DAYS_THRESHOLD)
        )
        # 游标分页
        if last_id:
            query = query.where(Discovery.id > last_id)
        query = query.order_by(Discovery.id).limit(BATCH_SIZE)

        rs = await db.execute(query)
        items = list(rs.scalars().all())
        if not items:
            break

        for d in items:
            try:
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
                created += 1
            except Exception as e:
                celery_task_logger.warning(
                    "创建离线告警失败",
                    discovery_id=str(d.id),
                    ip_address=d.ip_address,
                    error=str(e),
                )

        # 每批提交一次事务
        await db.commit()
        last_id = items[-1].id

    return created


async def _process_shadow_assets(
    db: AsyncSession,
    service: AlertService,
    notifier: NotificationService,
) -> int:
    """
    分批处理影子资产，使用游标分页。

    Args:
        db: 数据库会话
        service: 告警服务
        notifier: 通知服务

    Returns:
        创建的告警数量
    """
    created = 0
    last_id: UUID | None = None

    while True:
        query = (
            select(Discovery)
            .where(Discovery.is_deleted.is_(False))
            .where(Discovery.status == DiscoveryStatus.SHADOW.value)
        )
        if last_id:
            query = query.where(Discovery.id > last_id)
        query = query.order_by(Discovery.id).limit(BATCH_SIZE)

        rs = await db.execute(query)
        items = list(rs.scalars().all())
        if not items:
            break

        for d in items:
            try:
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
                created += 1
            except Exception as e:
                celery_task_logger.warning(
                    "创建影子资产告警失败",
                    discovery_id=str(d.id),
                    ip_address=d.ip_address,
                    error=str(e),
                )

        await db.commit()
        last_id = items[-1].id

    return created


async def _auto_close_recovered_offline_alerts(
    db: AsyncSession,
    service: AlertService,
) -> int:
    """
    自动关闭已恢复设备的离线告警。

    设备 offline_days < 阈值时，认为设备已恢复在线。
    """
    closed = 0
    last_id: UUID | None = None

    while True:
        # 查找已恢复在线的设备（offline_days < 阈值）且有关联的未关闭告警
        query = (
            select(Discovery)
            .where(Discovery.is_deleted.is_(False))
            .where(Discovery.offline_days < settings.ALERT_OFFLINE_DAYS_THRESHOLD)
            .where(Discovery.matched_device_id.isnot(None))
        )
        if last_id:
            query = query.where(Discovery.id > last_id)
        query = query.order_by(Discovery.id).limit(BATCH_SIZE)

        rs = await db.execute(query)
        items = list(rs.scalars().all())
        if not items:
            break

        for d in items:
            if d.matched_device_id:
                closed_count = await service.auto_close_offline_alerts(d.matched_device_id)
                closed += closed_count

        await db.commit()
        last_id = items[-1].id

    return closed


async def _auto_close_matched_shadow_alerts(
    db: AsyncSession,
    service: AlertService,
) -> int:
    """
    自动关闭已纳管的影子资产告警。

    Discovery.status == MATCHED 时，关闭相关影子资产告警。
    """
    closed = 0
    last_id: UUID | None = None

    while True:
        query = (
            select(Discovery)
            .where(Discovery.is_deleted.is_(False))
            .where(Discovery.status == DiscoveryStatus.MATCHED.value)
        )
        if last_id:
            query = query.where(Discovery.id > last_id)
        query = query.order_by(Discovery.id).limit(BATCH_SIZE)

        rs = await db.execute(query)
        items = list(rs.scalars().all())
        if not items:
            break

        for d in items:
            closed_count = await service.auto_close_shadow_alerts(d.id)
            closed += closed_count

        await db.commit()
        last_id = items[-1].id

    return closed


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.alerts.scheduled_offline_alerts",
    queue="discovery",
)
def scheduled_offline_alerts(self) -> dict[str, Any]:
    """
    定时扫描离线设备与影子资产，并生成告警。

    同时自动关闭已恢复或已纳管的告警。

    使用游标分页避免大数据量时内存溢出，每批处理后提交事务。

    - 离线阈值：settings.ALERT_OFFLINE_DAYS_THRESHOLD（默认 3 天）
    - 影子资产：Discovery.status == SHADOW
    """
    task_id = self.request.id
    started_at = datetime.now(UTC)

    async def _scan() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            service = AlertService(db, alert_crud)
            notifier = NotificationService()

            # 1. 自动关闭已恢复/已纳管的告警
            closed_offline = await _auto_close_recovered_offline_alerts(db, service)
            closed_shadow = await _auto_close_matched_shadow_alerts(db, service)

            # 2. 创建新告警
            created_offline = await _process_offline_devices(db, service, notifier)
            created_shadow = await _process_shadow_assets(db, service, notifier)

        return {
            "task_id": task_id,
            "created_offline": created_offline,
            "created_shadow": created_shadow,
            "closed_offline": closed_offline,
            "closed_shadow": closed_shadow,
        }

    try:
        result = run_async(_scan())
        ended_at = datetime.now(UTC)
        celery_task_logger.info(
            "告警扫描完成",
            task_id=task_id,
            created_offline=result.get("created_offline", 0),
            created_shadow=result.get("created_shadow", 0),
            closed_offline=result.get("closed_offline", 0),
            closed_shadow=result.get("closed_shadow", 0),
            duration_seconds=(ended_at - started_at).total_seconds(),
        )
        return result
    except Exception as e:
        celery_task_logger.error("告警扫描失败", task_id=task_id, error=str(e), exc_info=True)
        raise
