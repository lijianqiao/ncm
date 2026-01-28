"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template_approval.py
@DateTime: 2026-01-12 00:00:00
@Docs: TemplateApprovalStep CRUD（纯数据访问）。
"""

from uuid import UUID

from pydantic import BaseModel

from app.crud.base import CRUDBase
from app.models.template_approval import TemplateApprovalStep


class TemplateApprovalStepCreateSchema(BaseModel):
    """TemplateApprovalStep 创建 Schema（CRUD 内部使用）。"""

    template_id: UUID
    level: int

    model_config = {"extra": "allow"}


class TemplateApprovalStepUpdateSchema(BaseModel):
    """TemplateApprovalStep 更新 Schema（CRUD 内部使用）。"""

    model_config = {"extra": "allow"}


class CRUDTemplateApprovalStep(
    CRUDBase[TemplateApprovalStep, TemplateApprovalStepCreateSchema, TemplateApprovalStepUpdateSchema]
):
    """模板审批步骤 CRUD（纯数据访问，使用基类 get_paginated）。"""

    pass


template_approval_crud = CRUDTemplateApprovalStep(TemplateApprovalStep)
