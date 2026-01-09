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

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus, TaskStatus, TaskType
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.backup import Backup
    from app.models.user import User


class Task(AuditableModel):
    """任务模型。"""

    __tablename__ = "ncm_task"

    # 任务基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务名称")
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="任务类型")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务描述")

    # Celery 任务 ID
    celery_task_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True, comment="Celery 任务ID"
    )

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
    template_params: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="模板参数(JSON)"
    )

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
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审批时间"
    )
    approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审批意见")

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
    submitter: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[submitter_id], lazy="selectin"
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approver_id], lazy="selectin"
    )
    rollback_backup: Mapped[Optional["Backup"]] = relationship("Backup", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Task(name={self.name}, type={self.task_type}, status={self.status})>"
