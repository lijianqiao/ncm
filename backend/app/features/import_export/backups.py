"""
@Author: li
@Email: li
@FileName: backups.py
@DateTime: 2026/01/16
@Docs: 配置备份导出
"""

from typing import Any

import polars as pl
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import Backup
from app.models.device import Device


async def export_backups_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(Backup, Device.name, Device.ip_address)
        .join(Device, Device.id == Backup.device_id)
        .where(and_(Backup.is_deleted.is_(False), Device.is_deleted.is_(False)))
        .order_by(Backup.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for backup, device_name, device_ip in result.all():
        rows.append(
            {
                "device_name": device_name,
                "device_ip": device_ip,
                "backup_type": backup.backup_type,
                "status": backup.status,
                "content_size": backup.content_size,
                "md5_hash": backup.md5_hash,
                "operator_id": str(backup.operator_id) if backup.operator_id else "",
                "created_at": backup.created_at.isoformat() if backup.created_at else "",
                "updated_at": backup.updated_at.isoformat() if backup.updated_at else "",
            }
        )
    return pl.DataFrame(rows)

