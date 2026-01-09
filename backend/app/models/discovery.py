"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-09 15:00:00
@Docs: 设备发现模型 (Discovery) 定义。

用于存储网络扫描发现的设备信息，与 CMDB 比对发现影子资产。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DiscoveryStatus
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.device import Device


class Discovery(AuditableModel):
    """设备发现模型。"""

    __tablename__ = "ncm_discovery"

    # 网络信息
    ip_address: Mapped[str] = mapped_column(String(45), index=True, nullable=False, comment="IP 地址")
    mac_address: Mapped[str | None] = mapped_column(String(17), index=True, nullable=True, comment="MAC 地址")

    # 识别信息
    vendor: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="厂商(OUI 识别)")
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="设备类型推测")
    hostname: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="主机名")
    os_info: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="操作系统信息")

    # 端口信息
    open_ports: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="开放端口列表(JSON: {port: service})"
    )

    # SSH Banner 信息
    ssh_banner: Mapped[str | None] = mapped_column(Text, nullable=True, comment="SSH Banner")

    # 发现时间
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="首次发现时间"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="最后发现时间"
    )
    offline_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="离线天数")

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), default=DiscoveryStatus.PENDING.value, nullable=False, index=True, comment="发现状态"
    )

    # CMDB 匹配
    matched_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_device.id", ondelete="SET NULL"),
        nullable=True,
        comment="匹配的设备ID",
    )

    # 扫描来源
    scan_source: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="扫描来源(nmap/masscan)")
    scan_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="扫描任务ID")

    # 关联关系
    matched_device: Mapped[Optional["Device"]] = relationship("Device", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Discovery(ip={self.ip_address}, status={self.status})>"
