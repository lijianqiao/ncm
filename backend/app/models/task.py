"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: task.py
@DateTime: 2026-01-09 15:00:00
@Docs: 任务模型 (Task) 定义。

用于管理配置下发、备份等异步任务的状态跟踪和审批流程。
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus, TaskStatus
from app.models.base import AuditableModel
from app.utils.user_display import format_user_display_name

if TYPE_CHECKING:
    from app.models.backup import Backup
    from app.models.task_approval import TaskApprovalStep
    from app.models.template import Template
    from app.models.user import User


class Task(AuditableModel):
    """任务模型。"""

    __tablename__ = "ncm_task"
    __table_args__ = (
        Index("ix_ncm_task_created_at", "created_at"),
        {"comment": "任务表"},
    )

    # 任务基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务名称")
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="任务类型")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务描述")

    # Celery 任务 ID
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="Celery 任务ID")

    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, nullable=False, index=True, comment="任务状态"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="执行进度(0-100)")

    # 目标设备
    target_devices: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="目标设备列表(JSON: {device_ids: [...]})"
    )
    total_devices: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="设备总数")
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="成功数")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="失败数")

    # 执行结果
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="执行结果(JSON: {success: [...], failed: [...]})"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    # 模板与参数（配置下发任务使用）
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_template.id", ondelete="SET NULL"),
        nullable=True,
        comment="模板ID",
    )
    template_params: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="模板参数(JSON)")

    template: Mapped[Optional["Template"]] = relationship("Template", foreign_keys=[template_id], lazy="selectin")

    # 审批信息
    approval_status: Mapped[str] = mapped_column(
        String(20), default=ApprovalStatus.NONE.value, nullable=False, comment="审批状态"
    )
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变更说明")
    impact_scope: Mapped[str | None] = mapped_column(Text, nullable=True, comment="影响范围")
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True, comment="回退方案")

    # 提交人
    submitter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="提交人ID",
    )

    # 审批人
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="审批人ID",
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审批时间")
    approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审批意见")

    # Phase 4: 三级审批扩展（最小字段）
    approval_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否需要审批(下发任务默认需要)"
    )
    current_approval_level: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="当前已通过的审批级别(0-3)"
    )

    # 下发计划/灰度参数（JSON）
    deploy_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="下发计划(JSON)")

    # 执行时间
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="开始执行时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")

    # 回滚信息
    rollback_backup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_backup.id", ondelete="SET NULL"),
        nullable=True,
        comment="变更前配置备份ID(用于回滚)",
    )

    # 关联关系
    submitter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[submitter_id], lazy="selectin")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_id], lazy="selectin")
    rollback_backup: Mapped[Optional["Backup"]] = relationship("Backup", lazy="selectin")
    approval_steps: Mapped[list["TaskApprovalStep"]] = relationship(
        "TaskApprovalStep", back_populates="task", lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def created_by(self) -> uuid.UUID | None:
        return self.submitter_id

    @property
    def created_by_name(self) -> str | None:
        if not self.submitter:
            return None
        return format_user_display_name(self.submitter.nickname, self.submitter.username)

    @property
    def template_name(self) -> str | None:
        if not self.template:
            return None
        return self.template.name

    @property
    def approvals(self) -> list["TaskApprovalStep"]:
        return sorted(self.approval_steps or [], key=lambda x: x.level)

    def __repr__(self) -> str:
        return f"<Task(name={self.name}, type={self.task_type}, status={self.status})>"
