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

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DeviceType, TemplateStatus, TemplateType
from app.models.base import AuditableModel

if TYPE_CHECKING:
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
    parameters: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="参数定义(JSON Schema)"
    )

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
    parent: Mapped[Optional["Template"]] = relationship(
        "Template", remote_side="Template.id", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Template(name={self.name}, version={self.version}, status={self.status})>"
