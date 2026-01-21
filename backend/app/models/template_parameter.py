"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_parameter.py
@DateTime: 2026-01-21 00:00:00
@Docs: 模板参数定义模型（表单化）。

用于存储模板的参数定义，替代 JSON Schema 字符串，降低用户使用门槛。
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ParamType
from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.template import Template


class TemplateParameter(AuditableModel):
    """模板参数定义（表单化）。"""

    __tablename__ = "ncm_template_parameter"

    # 关联模板
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncm_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联模板ID",
    )

    # 基础信息
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="变量名（用于 Jinja2）")
    label: Mapped[str] = mapped_column(String(100), nullable=False, comment="显示名称")
    param_type: Mapped[str] = mapped_column(
        String(20), default=ParamType.STRING.value, nullable=False, comment="参数类型"
    )

    # 验证规则
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否必填")
    default_value: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="默认值")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="参数说明")

    # 类型相关约束
    options: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="下拉选项（select 类型时使用）"
    )
    min_value: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最小值（数值类型）")
    max_value: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最大值（数值类型）")
    pattern: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="正则校验表达式")

    # 显示控制
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="显示顺序")

    # 关联关系
    template: Mapped["Template"] = relationship("Template", back_populates="parameters_list")

    def __repr__(self) -> str:
        return f"<TemplateParameter(name={self.name}, type={self.param_type}, required={self.required})>"
