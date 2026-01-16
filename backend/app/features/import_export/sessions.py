"""
@Author: li
@Email: li
@FileName: sessions.py
@DateTime: 2026/01/16
@Docs: 在线会话导出
"""

from typing import Any

import polars as pl

from app.core.session_store import list_online_sessions


async def export_sessions_df(_db: Any) -> pl.DataFrame:
    page = 1
    page_size = 500
    rows: list[dict[str, Any]] = []

    while True:
        sessions, total = await list_online_sessions(page=page, page_size=page_size, keyword=None)
        for s in sessions:
            rows.append(
                {
                    "user_id": str(s.user_id),
                    "username": s.username,
                    "ip": s.ip or "",
                    "user_agent": s.user_agent or "",
                    "login_at": float(s.login_at),
                    "last_seen_at": float(s.last_seen_at),
                }
            )
        if page * page_size >= total:
            break
        page += 1

    return pl.DataFrame(rows)

