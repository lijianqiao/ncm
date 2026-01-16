"""
@Author: li
@Email: li
@FileName: logs.py
@DateTime: 2026/01/16
@Docs: 日志导出（登录日志 / 审计日志）
"""

import json
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import LoginLog, OperationLog


async def export_login_logs_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(LoginLog).where(LoginLog.is_deleted.is_(False)).order_by(LoginLog.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for line in result.scalars().all():
        rows.append(
            {
                "username": line.username or "",
                "ip": line.ip or "",
                "browser": line.browser or "",
                "os": line.os or "",
                "device": line.device or "",
                "user_agent": line.user_agent or "",
                "msg": line.msg or "",
                "status": bool(line.status),
                "created_at": line.created_at.isoformat() if line.created_at else "",
            }
        )
    return pl.DataFrame(rows)


async def export_operation_logs_df(db: AsyncSession) -> pl.DataFrame:
    result = await db.execute(
        select(OperationLog).where(OperationLog.is_deleted.is_(False)).order_by(OperationLog.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for line in result.scalars().all():
        rows.append(
            {
                "username": line.username or "",
                "module": line.module or "",
                "summary": line.summary or "",
                "method": line.method or "",
                "path": line.path or "",
                "params": json.dumps(line.params or {}, ensure_ascii=False),
                "response_code": line.response_code or 0,
                "duration": float(line.duration or 0),
                "ip": line.ip or "",
                "user_agent": line.user_agent or "",
                "created_at": line.created_at.isoformat() if line.created_at else "",
            }
        )
    return pl.DataFrame(rows)
