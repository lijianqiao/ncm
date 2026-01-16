"""
@Author: li
@Email: li
@FileName: inventory_audit.py
@DateTime: 2026/01/16
@Docs: 资产盘点导出
"""

import json
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_audit import InventoryAudit


async def export_inventory_audits_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(InventoryAudit).where(InventoryAudit.is_deleted.is_(False)).order_by(InventoryAudit.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for a in result.scalars().all():
        rows.append(
            {
                "name": a.name,
                "status": a.status,
                "scope": json.dumps(a.scope or {}, ensure_ascii=False),
                "result": json.dumps(a.result or {}, ensure_ascii=False),
                "error_message": a.error_message or "",
                "operator_id": str(a.operator_id) if a.operator_id else "",
                "started_at": a.started_at.isoformat() if a.started_at else "",
                "finished_at": a.finished_at.isoformat() if a.finished_at else "",
                "created_at": a.created_at.isoformat() if a.created_at else "",
                "updated_at": a.updated_at.isoformat() if a.updated_at else "",
            }
        )
    return pl.DataFrame(rows)

