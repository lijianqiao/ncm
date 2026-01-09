"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log.py
@DateTime: 2025-12-30 14:30:00
@Docs: 日志 Schema 定义。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LogBase(BaseModel):
    user_id: UUID | None = None
    username: str | None = None
    ip: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LoginLogBase(LogBase):
    user_agent: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None
    status: bool = True
    msg: str | None = None


class LoginLogCreate(LoginLogBase):
    created_at: datetime | None = None


class LoginLogResponse(LoginLogBase):
    id: UUID
    created_at: datetime


class OperationLogBase(LogBase):
    module: str | None = None
    summary: str | None = None
    method: str | None = None
    path: str | None = None
    params: Any | None = None
    response_code: int | None = None
    response_result: Any | None = None
    duration: float | None = None
    user_agent: str | None = None


class OperationLogCreate(OperationLogBase):
    created_at: datetime | None = None


class OperationLogResponse(OperationLogBase):
    id: UUID
    created_at: datetime
