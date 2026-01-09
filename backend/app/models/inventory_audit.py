"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: inventory_audit.py
@DateTime: 2026-01-09 21:15:00
@Docs: 资产盘点任务模型 (InventoryAudit)。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InventoryAuditStatus
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.user import User


class InventoryAudit(AuditableModel):
    """资产盘点任务。"""

    __tablename__ = "ncm_inventory_audit"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="盘点任务名称")
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, comment="盘点范围(JSON)")
    status: Mapped[str] = mapped_column(
        String(20),
        default=InventoryAuditStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="盘点状态",
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="盘点结果(JSON)")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="结束时间")

    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人ID",
    )
    operator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[operator_id], lazy="selectin")

    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="Celery任务ID")

