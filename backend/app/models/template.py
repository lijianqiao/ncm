"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template.py
@DateTime: 2026-01-09 15:00:00
@Docs: 配置模板模型 (Template) 定义。

用于存储 Jinja2 配置模板，支持多厂商、版本控制。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ApprovalStatus, DeviceType, TemplateStatus, TemplateType
from app.models.base import AuditableModel
from app.utils.user_display import format_user_display_name

if TYPE_CHECKING:
    from app.models.template_approval import TemplateApprovalStep
    from app.models.user import User


class Template(AuditableModel):
    """配置模板模型。"""

    __tablename__ = "ncm_template"

    # 基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="模板描述")
    template_type: Mapped[str] = mapped_column(
        String(20), default=TemplateType.CUSTOM.value, nullable=False, comment="模板类型"
    )

    # 模板内容
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Jinja2 模板内容")

    # 适用厂商（支持多选）
    vendors: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, comment="适用厂商列表(h3c/huawei/cisco/other)"
    )

    # 适用设备类型
    device_type: Mapped[str] = mapped_column(
        String(20), default=DeviceType.ALL.value, nullable=False, comment="适用设备类型"
    )

    # 参数定义（JSON Schema 格式）
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True, comment="参数定义(JSON Schema)")

    # 版本管理
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="版本号")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ncm_template.id", ondelete="SET NULL"),
        nullable=True,
        comment="父版本ID",
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), default=TemplateStatus.DRAFT.value, nullable=False, comment="模板状态"
    )

    # Phase 4: 复用“下发任务”三级审批模型（最小字段）
    approval_required: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否需要审批(模板默认需要)",
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStatus.NONE.value,
        nullable=False,
        comment="审批状态",
    )
    current_approval_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="当前已通过的审批级别(0-3)",
    )

    # 创建人
    creator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )

    # 使用统计
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="使用次数")

    # 关联关系
    creator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    parent: Mapped[Optional["Template"]] = relationship("Template", remote_side="Template.id", lazy="selectin")

    approval_steps: Mapped[list["TemplateApprovalStep"]] = relationship(
        "TemplateApprovalStep",
        back_populates="template",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def created_by(self) -> uuid.UUID | None:
        return self.creator_id

    @property
    def created_by_name(self) -> str | None:
        if not self.creator:
            return None
        return format_user_display_name(self.creator.nickname, self.creator.username)

    @property
    def approvals(self) -> list["TemplateApprovalStep"]:
        return sorted(self.approval_steps or [], key=lambda x: x.level)

    def __repr__(self) -> str:
        return f"<Template(name={self.name}, version={self.version}, status={self.status})>"
