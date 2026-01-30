"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology.py
@DateTime: 2026-01-09 23:00:00
@Docs: 网络拓扑模型 (Topology Models).

用于存储 LLDP/CDP 采集的网络拓扑链路信息。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.device import Device


class TopologyLink(AuditableModel):
    """网络拓扑链路模型。

    网络拓扑链路表，用于存储 LLDP/CDP 采集的网络拓扑链路信息。

    Attributes:
        source_device_id (UUID): 源设备 ID（本地设备）。
        source_interface (str): 源接口名称。
        target_device_id (UUID | None): 目标设备 ID（如果在 CMDB 中）。
        target_interface (str | None): 目标接口名称。
        target_hostname (str | None): 目标主机名（LLDP 上报）。
        target_ip (str | None): 目标管理 IP（LLDP 上报）。
        target_mac (str | None): 目标 MAC 地址或 Chassis ID。
        target_description (str | None): 目标设备描述。
        link_type (str): 链路类型（lldp/cdp/manual）。
        link_speed (str | None): 链路速率。
        link_status (str | None): 链路状态。
        collected_at (datetime): 采集时间。
        source_device (Device | None): 源设备对象。
        target_device (Device | None): 目标设备对象。
    """

    __tablename__ = "ncm_topology_link"
    __table_args__ = (
        Index(
            "uq_ncm_topology_link_source_iface_not_deleted",
            "source_device_id",
            "source_interface",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint(
            "link_type IN ('lldp', 'cdp', 'manual')",
            name="ck_ncm_topology_link_type",
        ),
        {"comment": "网络拓扑链路表"},
    )

    # 源设备（本地设备）
    source_device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncm_device.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="源设备ID",
    )
    source_interface: Mapped[str] = mapped_column(String(100), nullable=False, comment="源接口名称")

    # 目标设备（邻居设备）
    target_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_device.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="目标设备ID（如果在 CMDB 中）",
    )
    target_interface: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标接口名称")
    target_hostname: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="目标主机名（LLDP 上报）")
    target_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="目标管理 IP（LLDP 上报）")
    target_mac: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标 MAC 地址或 Chassis ID")
    target_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="目标设备描述")

    # 链路属性
    link_type: Mapped[str] = mapped_column(
        String(20), default="lldp", nullable=False, comment="链路类型(lldp/cdp/manual)"
    )
    link_speed: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="链路速率")
    link_status: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="链路状态")

    # 采集时间
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="采集时间")

    # 关联关系
    source_device: Mapped[Optional["Device"]] = relationship(
        "Device",
        foreign_keys=[source_device_id],
        lazy="selectin",
    )
    target_device: Mapped[Optional["Device"]] = relationship(
        "Device",
        foreign_keys=[target_device_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TopologyLink({self.source_interface} -> {self.target_hostname}:{self.target_interface})>"
