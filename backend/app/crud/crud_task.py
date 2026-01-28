"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_task.py
@DateTime: 2026-01-09 23:00:00
@Docs: 任务 CRUD 操作。

提供任务（配置下发、备份等）的数据库操作，支持关联加载审批步骤和提交人信息。
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.crud.base import CRUDBase
from app.models.task import Task
from app.models.task_approval import TaskApprovalStep


class TaskCreateSchema(BaseModel):
    """
    Task 创建 Schema（CRUD 内部使用）。

    由于 Task 模型字段较多，CRUD 层使用宽松的 Schema 允许任意字段传入，
    实际字段验证由 Service 层或 API 层的 Schema 负责。
    """

    task_type: str | None = None
    status: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class TaskUpdateSchema(BaseModel):
    """
    Task 更新 Schema（CRUD 内部使用）。

    同 TaskCreateSchema，采用宽松模式以支持任意字段更新。
    """

    task_type: str | None = None
    status: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class CRUDTask(CRUDBase[Task, TaskCreateSchema, TaskUpdateSchema]):
    """任务 CRUD 操作类。"""

    @staticmethod
    def _related_options() -> Sequence[Any]:
        """返回关联加载选项列表（提交人、模板、审批步骤）。"""
        return [
            selectinload(Task.submitter),
            selectinload(Task.template),
            selectinload(Task.approval_steps).selectinload(TaskApprovalStep.approver),
            with_loader_criteria(TaskApprovalStep, TaskApprovalStep.is_deleted.is_(False), include_aliases=True),
        ]

    # 公开 _related_options 供服务层使用
    RELATED_OPTIONS = property(lambda self: self._related_options())


task_crud = CRUDTask(Task)
