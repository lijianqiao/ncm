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
    """日志基础 Schema。

    日志的基础字段定义。

    Attributes:
        user_id (UUID | None): 用户 ID。
        username (str | None): 用户名。
        ip (str | None): IP 地址。
    """

    user_id: UUID | None = None
    username: str | None = None
    ip: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LoginLogBase(LogBase):
    """登录日志基础 Schema。

    登录日志的基础字段定义。

    Attributes:
        user_agent (str | None): 用户代理字符串。
        browser (str | None): 浏览器类型。
        os (str | None): 操作系统类型。
        device (str | None): 设备类型。
        status (bool): 登录状态（成功/失败），默认 True。
        msg (str | None): 登录消息。
    """

    user_agent: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None
    status: bool = True
    msg: str | None = None


class LoginLogCreate(LoginLogBase):
    """创建登录日志请求 Schema。

    用于创建登录日志的请求体。

    Attributes:
        created_at (datetime | None): 创建时间。
    """

    created_at: datetime | None = None


class LoginLogResponse(LoginLogBase):
    """登录日志响应 Schema。

    用于返回登录日志信息的响应体。

    Attributes:
        id (UUID): 日志 ID。
        created_at (datetime): 创建时间。
    """

    id: UUID
    created_at: datetime


class OperationLogBase(LogBase):
    """操作日志基础 Schema。

    操作日志的基础字段定义。

    Attributes:
        module (str | None): 操作模块。
        summary (str | None): 操作摘要。
        method (str | None): HTTP 方法。
        path (str | None): 请求路径。
        params (Any | None): 请求参数。
        response_code (int | None): 响应状态码。
        response_result (Any | None): 响应结果。
        duration (float | None): 请求耗时（秒）。
        user_agent (str | None): 用户代理字符串。
    """

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
    """创建操作日志请求 Schema。

    用于创建操作日志的请求体。

    Attributes:
        created_at (datetime | None): 创建时间。
    """

    created_at: datetime | None = None


class OperationLogResponse(OperationLogBase):
    """操作日志响应 Schema。

    用于返回操作日志信息的响应体。

    Attributes:
        id (UUID): 日志 ID。
        created_at (datetime): 创建时间。
    """

    id: UUID
    created_at: datetime
