"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log.py
@DateTime: 2025-12-30 11:47:00
@Docs: Log models for audit and login tracking.
"""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditableModel


class LoginLog(AuditableModel):
    __tablename__ = "sys_login_log"
    __table_args__ = (
        Index("ix_sys_login_log_created_at", "created_at"),
        {"comment": "登录日志表"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(50), nullable=True)
    os: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device: Mapped[str | None] = mapped_column(String(50), nullable=True)
    msg: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True)  # Success/Fail


class OperationLog(AuditableModel):
    __tablename__ = "sys_operation_log"
    __table_args__ = (
        Index("ix_sys_operation_log_created_at", "created_at"),
        {"comment": "操作日志表"},
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    params: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
