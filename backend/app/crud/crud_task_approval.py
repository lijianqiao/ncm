"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_task_approval.py
@DateTime: 2026-01-09 23:00:00
@Docs: TaskApprovalStep CRUD（纯数据访问）。
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.crud.base import CRUDBase
from app.models.task_approval import TaskApprovalStep


class TaskApprovalStepCreateSchema(BaseModel):
    """TaskApprovalStep 创建 Schema（CRUD 内部使用）。"""

    task_id: UUID
    level: int
    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class TaskApprovalStepUpdateSchema(BaseModel):
    """TaskApprovalStep 更新 Schema（CRUD 内部使用）。"""

    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class CRUDTaskApprovalStep(CRUDBase[TaskApprovalStep, TaskApprovalStepCreateSchema, TaskApprovalStepUpdateSchema]):
    """任务审批步骤 CRUD（纯数据访问，使用基类 get_paginated）。"""

    pass


task_approval_crud = CRUDTaskApprovalStep(TaskApprovalStep)
