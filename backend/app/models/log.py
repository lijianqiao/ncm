"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log.py
@DateTime: 2025-12-30 11:47:00
@Docs: Log models for audit and login tracking.
"""

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditableModel


class LoginLog(AuditableModel):
    """登录日志模型。

    用户登录日志表，记录用户登录的详细信息，用于安全审计和登录分析。

    Attributes:
        user_id (UUID | None): 用户 ID。
        username (str | None): 用户名。
        ip (str | None): IP 地址。
        user_agent (str | None): 用户代理字符串。
        browser (str | None): 浏览器类型。
        os (str | None): 操作系统类型。
        device (str | None): 设备类型。
        msg (str | None): 登录消息。
        status (bool): 登录状态（成功/失败）。
    """

    __tablename__ = "sys_login_log"
    __table_args__ = (
        Index("ix_sys_login_log_created_at", "created_at"),
        {"comment": "登录日志表"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True, comment="用户ID"
    )
    username: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="用户名")
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="IP地址")
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="用户代理")
    browser: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="浏览器")
    os: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="操作系统")
    device: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="设备类型")
    msg: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="登录消息")
    status: Mapped[bool] = mapped_column(Boolean, default=True, comment="登录状态(成功/失败)")

    def __repr__(self) -> str:
        return f"<LoginLog(username={self.username}, ip={self.ip}, status={self.status})>"


class OperationLog(AuditableModel):
    """操作日志模型。

    操作日志表，记录用户的操作行为，用于审计和问题排查。

    Attributes:
        user_id (UUID | None): 用户 ID。
        username (str | None): 用户名。
        module (str | None): 操作模块。
        summary (str | None): 操作摘要。
        method (str | None): HTTP 方法。
        path (str | None): 请求路径。
        params (Any | None): 请求参数（JSONB）。
        response_code (int | None): 响应状态码。
        response_result (Any | None): 响应结果（JSONB）。
        duration (float | None): 请求耗时（秒）。
        ip (str | None): IP 地址。
        user_agent (str | None): 用户代理字符串。
    """

    __tablename__ = "sys_operation_log"
    __table_args__ = (
        Index("ix_sys_operation_log_created_at", "created_at"),
        {"comment": "操作日志表"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True, comment="用户ID"
    )
    username: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="用户名")
    module: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="操作模块")
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="操作摘要")
    method: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="HTTP方法")
    path: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="请求路径")
    params: Mapped[Any | None] = mapped_column(JSONB, nullable=True, comment="请求参数(JSONB)")
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应状态码")
    response_result: Mapped[Any | None] = mapped_column(JSONB, nullable=True, comment="响应结果(JSONB)")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True, comment="请求耗时(秒)")
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="IP地址")
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="用户代理")

    def __repr__(self) -> str:
        return f"<OperationLog(username={self.username}, module={self.module}, method={self.method})>"
