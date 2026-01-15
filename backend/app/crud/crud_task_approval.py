"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_task_approval.py
@DateTime: 2026-01-09 23:00:00
@Docs: TaskApprovalStep CRUD。
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    async def get_by_task_and_level(self, db: AsyncSession, *, task_id, level: int) -> TaskApprovalStep | None:
        stmt = select(TaskApprovalStep).where(
            TaskApprovalStep.task_id == task_id,
            TaskApprovalStep.level == level,
            TaskApprovalStep.is_deleted.is_(False),
        )
        return (await db.execute(stmt)).scalars().first()

    async def list_by_task(self, db: AsyncSession, *, task_id) -> list[TaskApprovalStep]:
        stmt = (
            select(TaskApprovalStep)
            .where(TaskApprovalStep.task_id == task_id, TaskApprovalStep.is_deleted.is_(False))
            .order_by(TaskApprovalStep.level.asc())
        )
        return list((await db.execute(stmt)).scalars().all())


task_approval_crud = CRUDTaskApprovalStep(TaskApprovalStep)
