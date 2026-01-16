"""
@Author: li
@Email: li
@FileName: templates.py
@DateTime: 2026/01/16
@Docs: 模板库导出
"""

import json
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template


async def export_templates_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(select(Template).where(Template.is_deleted.is_(False)).order_by(Template.updated_at.desc()))
    rows: list[dict[str, Any]] = []
    for t in result.scalars().all():
        submitted_at = ""
        if t.approval_steps:
            submit_times = [s.created_at for s in t.approval_steps if s.created_at]
            if submit_times:
                submitted_at = min(submit_times).isoformat()

        approved_at = ""
        approved_by = ""
        if t.approval_steps:
            approved_steps = [s for s in t.approval_steps if s.approved_at]
            if approved_steps:
                latest = max(approved_steps, key=lambda s: s.approved_at or 0)
                if latest.approved_at:
                    approved_at = latest.approved_at.isoformat()
                if latest.approver_id:
                    approved_by = str(latest.approver_id)

        rows.append(
            {
                "name": t.name,
                "template_type": t.template_type,
                "vendors": json.dumps(t.vendors or [], ensure_ascii=False),
                "device_type": t.device_type or "",
                "description": t.description or "",
                "parameters": json.dumps(t.parameters or {}, ensure_ascii=False),
                "content": t.content,
                "version": t.version,
                "status": t.status,
                "submitted_at": submitted_at,
                "approved_at": approved_at,
                "approved_by": approved_by,
                "created_at": t.created_at.isoformat() if t.created_at else "",
                "updated_at": t.updated_at.isoformat() if t.updated_at else "",
            }
        )
    return pl.DataFrame(rows)
