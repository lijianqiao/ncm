"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup.py
@DateTime: 2026-01-09 15:00:00
@Docs: 配置备份模型 (Backup) 定义。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import BackupStatus, BackupType
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.user import User


class Backup(AuditableModel):
    """配置备份模型。"""

    __tablename__ = "ncm_backup"
    __table_args__ = (
        Index("ix_ncm_backup_device_time", "device_id", "created_at"),
        {"comment": "配置备份表"},
    )

    # 关联设备
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncm_device.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="设备ID",
    )

    # 备份内容
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="配置内容(小配置直接存储)")
    content_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="MinIO 存储路径(大配置)")
    content_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, comment="配置大小(字节)")

    # 备份元信息
    backup_type: Mapped[str] = mapped_column(
        String(20), default=BackupType.MANUAL.value, nullable=False, comment="备份类型"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=BackupStatus.SUCCESS.value, nullable=False, comment="备份状态"
    )
    md5_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="MD5 哈希值")

    # 操作人
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人ID",
    )

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    # 关联关系
    device: Mapped[Optional["Device"]] = relationship("Device", back_populates="backups", lazy="selectin")
    operator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Backup(device_id={self.device_id}, type={self.backup_type}, status={self.status})>"
