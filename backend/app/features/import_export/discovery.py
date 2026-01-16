"""
@Author: li
@Email: li
@FileName: discovery.py
@DateTime: 2026/01/16
@Docs: 设备发现导出
"""

import json
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dept import Department
from app.models.discovery import Discovery


async def export_discovery_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(Discovery, Department.code, Department.name)
        .join(Department, Department.id == Discovery.dept_id, isouter=True)
        .where(Discovery.is_deleted.is_(False))
        .order_by(Discovery.last_seen_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for d, dept_code, dept_name in result.all():
        rows.append(
            {
                "ip_address": d.ip_address,
                "mac_address": d.mac_address or "",
                "vendor": d.vendor or "",
                "device_type": d.device_type or "",
                "hostname": d.hostname or "",
                "os_info": d.os_info or "",
                "serial_number": d.serial_number or "",
                "open_ports": json.dumps(d.open_ports or {}, ensure_ascii=False),
                "ssh_banner": d.ssh_banner or "",
                "first_seen_at": d.first_seen_at.isoformat() if d.first_seen_at else "",
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else "",
                "offline_days": d.offline_days,
                "status": d.status,
                "scan_source": d.scan_source or "",
                "scan_task_id": d.scan_task_id or "",
                "dept_code": str(dept_code) if dept_code else "",
                "dept_name": str(dept_name) if dept_name else "",
                "snmp_ok": d.snmp_ok,
                "snmp_sysname": d.snmp_sysname or "",
                "snmp_sysdescr": d.snmp_sysdescr or "",
                "snmp_error": d.snmp_error or "",
                "created_at": d.created_at.isoformat() if d.created_at else "",
                "updated_at": d.updated_at.isoformat() if d.updated_at else "",
            }
        )
    return pl.DataFrame(rows)

