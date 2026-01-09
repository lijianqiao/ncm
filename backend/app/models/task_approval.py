"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: task_approval.py
@DateTime: 2026-01-09 23:00:00
@Docs: 下发任务审批步骤模型 (TaskApprovalStep).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskApprovalStep(AuditableModel):
    """任务审批步骤（用于三级审批）。"""

    __tablename__ = "ncm_task_approval_step"
    __table_args__ = (UniqueConstraint("task_id", "level", name="uq_task_level"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncm_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="任务ID",
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, comment="审批级别(1-3)")

    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="审批人ID",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="审批状态",
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审批意见")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审批时间")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用(保留字段)")

    task: Mapped["Task"] = relationship("Task", back_populates="approval_steps", lazy="selectin")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_id], lazy="selectin")
