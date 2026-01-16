"""
@Author: li
@Email: li
@FileName: alerts.py
@DateTime: 2026/01/16
@Docs: 告警中心导出
"""

import json
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.device import Device
from app.models.discovery import Discovery


async def export_alerts_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(Alert, Device.name, Device.ip_address, Discovery.ip_address)
        .join(Device, Device.id == Alert.related_device_id, isouter=True)
        .join(Discovery, Discovery.id == Alert.related_discovery_id, isouter=True)
        .where(Alert.is_deleted.is_(False))
        .order_by(Alert.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for a, device_name, device_ip, discovery_ip in result.all():
        rows.append(
            {
                "alert_type": a.alert_type,
                "severity": a.severity,
                "status": a.status,
                "title": a.title,
                "message": a.message or "",
                "source": a.source or "",
                "details": json.dumps(a.details or {}, ensure_ascii=False),
                "related_device_name": device_name or "",
                "related_device_ip": device_ip or "",
                "related_discovery_ip": discovery_ip or "",
                "created_at": a.created_at.isoformat() if a.created_at else "",
                "updated_at": a.updated_at.isoformat() if a.updated_at else "",
            }
        )
    return pl.DataFrame(rows)

