"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert.py
@DateTime: 2026-01-10 03:00:00
@Docs: 告警模型 (Alert) 定义。

用于存储配置变更、设备离线、影子资产等告警事件。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AlertSeverity, AlertStatus, AlertType
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.discovery import Discovery
    from app.models.user import User


class Alert(AuditableModel):
    """告警事件模型。"""

    __tablename__ = "ncm_alert"

    alert_type: Mapped[str] = mapped_column(
        String(30),
        default=AlertType.CONFIG_CHANGE.value,
        nullable=False,
        index=True,
        comment="告警类型(config_change/device_offline/shadow_asset)",
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        default=AlertSeverity.MEDIUM.value,
        nullable=False,
        index=True,
        comment="告警级别(low/medium/high)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=AlertStatus.OPEN.value,
        nullable=False,
        index=True,
        comment="告警状态(open/ack/closed)",
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="告警标题")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="告警正文")

    details: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="告警详情(JSON)")

    source: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="告警来源(diff/discovery/manual)")

    related_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_device.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联设备ID",
    )

    related_discovery_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_discovery.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联发现记录ID",
    )

    # 确认人信息
    acked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="确认人ID",
    )
    acked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="确认时间",
    )

    # 关闭人信息
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="关闭人ID",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="关闭时间",
    )

    # 关联关系
    related_device: Mapped[Optional["Device"]] = relationship("Device", lazy="selectin")
    related_discovery: Mapped[Optional["Discovery"]] = relationship("Discovery", lazy="selectin")
    acked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[acked_by_id], lazy="selectin")
    closed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[closed_by_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<Alert(type={self.alert_type}, severity={self.severity}, status={self.status})>"
