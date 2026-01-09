"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: device.py
@DateTime: 2026-01-09 15:00:00
@Docs: 网络设备模型 (Device) 定义。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AuthType, DeviceGroup, DeviceStatus, DeviceVendor
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.backup import Backup
    from app.models.dept import Department


class Device(AuditableModel):
    """网络设备模型。"""

    __tablename__ = "ncm_device"

    # 基础信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="设备名称/主机名")
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, index=True, nullable=False, comment="IP 地址")
    vendor: Mapped[str] = mapped_column(String(20), default=DeviceVendor.H3C.value, nullable=False, comment="厂商")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="设备型号")
    platform: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="平台类型(cisco_iosxe/huawei_vrp/hp_comware)"
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="物理位置")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="设备描述")

    # 连接信息
    ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False, comment="SSH 端口")

    # 认证关联字段
    auth_type: Mapped[str] = mapped_column(
        String(20), default=AuthType.OTP_SEED.value, nullable=False, comment="认证类型"
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="SSH 用户名(仅 static 类型)")
    password_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="加密后的静态密码(仅 static 类型)"
    )

    # 部门与设备分组（用于 OTP 凭据查询）
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_dept.id"), nullable=True, index=True, comment="所属部门ID(区域)"
    )
    device_group: Mapped[str] = mapped_column(
        String(20), default=DeviceGroup.ACCESS.value, nullable=False, index=True, comment="设备分组(core/distribution/access)"
    )

    # 生命周期
    status: Mapped[str] = mapped_column(
        String(20), default=DeviceStatus.IN_USE.value, nullable=False, comment="设备状态"
    )
    stock_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="入库时间")
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="领用人")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="报废时间")

    # 扩展信息
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="序列号")
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="操作系统版本")
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后备份时间")
    last_online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后在线时间")

    # 关联关系
    dept: Mapped[Optional["Department"]] = relationship("Department", lazy="selectin")
    backups: Mapped[list["Backup"]] = relationship("Backup", back_populates="device", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Device(name={self.name}, ip={self.ip_address}, vendor={self.vendor})>"
