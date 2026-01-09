"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_task_approval.py
@DateTime: 2026-01-09 23:00:00
@Docs: TaskApprovalStep CRUD。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.task_approval import TaskApprovalStep


class CRUDTaskApprovalStep(CRUDBase[TaskApprovalStep, dict, dict]):
    async def get_by_task_and_level(self, db: AsyncSession, *, task_id, level: int) -> TaskApprovalStep | None:
        stmt = select(TaskApprovalStep).where(TaskApprovalStep.task_id == task_id, TaskApprovalStep.level == level)
        return (await db.execute(stmt)).scalars().first()

    async def list_by_task(self, db: AsyncSession, *, task_id) -> list[TaskApprovalStep]:
        stmt = select(TaskApprovalStep).where(TaskApprovalStep.task_id == task_id).order_by(TaskApprovalStep.level.asc())
        return list((await db.execute(stmt)).scalars().all())


task_approval_crud = CRUDTaskApprovalStep(TaskApprovalStep)

