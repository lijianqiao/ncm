"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: session.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话相关 Schema.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OnlineSessionResponse(BaseModel):
    user_id: UUID
    username: str
    ip: str | None = None
    user_agent: str | None = None
    login_at: datetime = Field(..., description="登录时间")
    last_seen_at: datetime = Field(..., description="最后活跃时间")


class KickUsersRequest(BaseModel):
    user_ids: list[UUID] = Field(..., description="要强制下线的用户ID列表")
