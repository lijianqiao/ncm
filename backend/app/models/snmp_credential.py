"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: snmp_credential.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据模型定义。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.dept import Department


class DeptSnmpCredential(AuditableModel):
    """部门 SNMP 凭据模型。"""

    __tablename__ = "ncm_dept_snmp_credential"
    __table_args__ = (
        UniqueConstraint("dept_id", name="uq_dept_snmp_credential_dept_id"),
        {"comment": "部门 SNMP 凭据表"},
    )

    dept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_dept.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="部门ID",
    )

    snmp_version: Mapped[str] = mapped_column(String(10), default="v2c", nullable=False, comment="SNMP 版本(v2c/v3)")
    port: Mapped[int] = mapped_column(Integer, default=161, nullable=False, comment="SNMP 端口")

    community_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="SNMP 团体字串（加密存储）")

    v3_username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="SNMPv3 用户名")
    v3_auth_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="SNMPv3 Auth Key（加密）")
    v3_priv_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="SNMPv3 Priv Key（加密）")
    v3_auth_proto: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="SNMPv3 Auth 协议")
    v3_priv_proto: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="SNMPv3 Priv 协议")
    v3_security_level: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="SNMPv3 安全级别")

    description: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="描述")

    dept: Mapped[Optional["Department"]] = relationship("Department", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeptSnmpCredential(dept_id={self.dept_id}, version={self.snmp_version}, port={self.port})>"
