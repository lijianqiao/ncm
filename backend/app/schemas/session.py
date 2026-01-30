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
    """在线会话响应 Schema。

    用于返回在线会话信息的响应体。

    Attributes:
        user_id (UUID): 用户 ID。
        username (str): 用户名。
        ip (str | None): IP 地址。
        user_agent (str | None): 用户代理字符串。
        login_at (datetime): 登录时间。
        last_seen_at (datetime): 最后活跃时间。
    """

    user_id: UUID
    username: str
    ip: str | None = None
    user_agent: str | None = None
    login_at: datetime = Field(..., description="登录时间")
    last_seen_at: datetime = Field(..., description="最后活跃时间")


class KickUsersRequest(BaseModel):
    """强制下线用户请求 Schema。

    用于强制下线用户的请求体。

    Attributes:
        user_ids (list[UUID]): 要强制下线的用户 ID 列表。
    """

    user_ids: list[UUID] = Field(..., description="要强制下线的用户ID列表")
