"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_approval.py
@DateTime: 2026-01-12 00:00:00
@Docs: 模板审批步骤模型 (TemplateApprovalStep).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.template import Template
    from app.models.user import User


class TemplateApprovalStep(AuditableModel):
    """模板审批步骤模型（用于三级审批）。

    模板审批步骤表，用于管理模板的三级审批流程。

    Attributes:
        template_id (UUID): 模板 ID。
        level (int): 审批级别（1-3）。
        approver_id (UUID | None): 审批人 ID。
        status (str): 审批状态（PENDING/APPROVED/REJECTED）。
        comment (str | None): 审批意见。
        approved_at (datetime | None): 审批时间。
        is_active (bool): 是否启用（保留字段）。
        template (Template): 关联的模板对象。
        approver (User | None): 审批人对象。
    """

    __tablename__ = "ncm_template_approval_step"
    __table_args__ = (UniqueConstraint("template_id", "level", name="uq_template_level"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncm_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="模板ID",
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

    template: Mapped["Template"] = relationship("Template", back_populates="approval_steps", lazy="selectin")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_id], lazy="selectin")

    @property
    def approver_name(self) -> str | None:
        if not self.approver:
            return None
        nickname = (self.approver.nickname or "").strip()
        username = (self.approver.username or "").strip()
        if nickname and username:
            return f"{nickname}({username})"
        return nickname or username or None
