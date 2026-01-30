"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credential.py
@DateTime: 2026-01-09 15:00:00
@Docs: 设备分组凭据模型 (DeviceGroupCredential) 定义。

按"部门 + 设备分组"管理凭据：
- 每个"部门 + 设备分组"组合对应一个独立的账号 + OTP 种子
- 同一时间下，同部门的核心、汇聚、接入层 OTP 动态验证码各不相同
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AuthType, DeviceGroup
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.dept import Department


class DeviceGroupCredential(AuditableModel):
    """设备分组凭据模型。

    按"部门 + 设备分组"管理 OTP 凭据：
    - dept_id + device_group 作为复合唯一键
    - 每个凭据包含独立的账号 + OTP 种子
    - 同一时间下，同部门的核心、汇聚、接入层 OTP 动态验证码各不相同

    Attributes:
        dept_id (UUID): 部门 ID（区域）。
        device_group (str): 设备分组（core/distribution/access）。
        username (str): SSH 账号。
        otp_seed_encrypted (str | None): OTP 种子（AES-256 加密存储）。
        auth_type (str): 认证类型（otp_seed/otp_manual）。
        description (str | None): 凭据描述（如：华北机房A-核心层设备账号）。
        dept (Department | None): 所属部门对象。
    """

    __tablename__ = "ncm_device_group_credential"
    __table_args__ = (
        UniqueConstraint("dept_id", "device_group", name="uq_dept_device_group"),
        {"comment": "部门设备分组凭据表"},
    )

    # 部门关联（顶级部门 = 区域）
    dept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_dept.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="部门ID(区域)",
    )

    # 设备分组
    device_group: Mapped[str] = mapped_column(
        String(20),
        default=DeviceGroup.ACCESS.value,
        nullable=False,
        index=True,
        comment="设备分组(core/distribution/access)",
    )

    # 凭据信息
    username: Mapped[str] = mapped_column(String(100), nullable=False, comment="SSH 账号")
    otp_seed_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OTP 种子(AES-256 加密存储)"
    )

    # 认证类型
    auth_type: Mapped[str] = mapped_column(
        String(20),
        default=AuthType.OTP_SEED.value,
        nullable=False,
        comment="认证类型(otp_seed/otp_manual)",
    )

    # 描述
    description: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="凭据描述(如:华北机房A-核心层设备账号)"
    )

    # 关联关系
    dept: Mapped[Optional["Department"]] = relationship("Department", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeviceGroupCredential(dept_id={self.dept_id}, group={self.device_group}, username={self.username})>"
