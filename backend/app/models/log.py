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
    """登录日志模型。"""

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
    """操作日志模型。"""

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
