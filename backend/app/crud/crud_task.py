"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_task.py
@DateTime: 2026-01-09 23:00:00
@Docs: Task CRUD。
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.crud.base import CRUDBase
from app.models.task import Task
from app.models.task_approval import TaskApprovalStep


class TaskCreateSchema(BaseModel):
    """Task 创建 Schema（CRUD 内部使用）。"""

    task_type: str | None = None
    status: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class TaskUpdateSchema(BaseModel):
    """Task 更新 Schema（CRUD 内部使用）。"""

    task_type: str | None = None
    status: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class CRUDTask(CRUDBase[Task, TaskCreateSchema, TaskUpdateSchema]):
    @staticmethod
    def _with_related(stmt):
        return stmt.options(
            selectinload(Task.submitter),
            selectinload(Task.template),
            selectinload(Task.approval_steps).selectinload(TaskApprovalStep.approver),
            with_loader_criteria(TaskApprovalStep, TaskApprovalStep.is_deleted.is_(False), include_aliases=True),
        )

    async def get_with_related(self, db: AsyncSession, *, id) -> Task | None:
        stmt = select(Task).where(Task.id == id, Task.is_deleted.is_(False))
        stmt = self._with_related(stmt)
        return (await db.execute(stmt)).scalars().first()

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        task_type: str | None = None,
        status: str | None = None,
        with_related: bool = False,
    ) -> tuple[list[Task], int]:
        page, page_size = self._validate_pagination(page, page_size)

        stmt = select(Task).where(Task.is_deleted.is_(False))
        count_stmt = select(func.count(Task.id)).where(Task.is_deleted.is_(False))

        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
            count_stmt = count_stmt.where(Task.task_type == task_type)
        if status:
            stmt = stmt.where(Task.status == status)
            count_stmt = count_stmt.where(Task.status == status)

        if with_related:
            stmt = self._with_related(stmt)

        stmt = stmt.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        task_type: str | None = None,
        status: str | None = None,
        with_related: bool = False,
    ) -> tuple[list[Task], int]:
        page, page_size = self._validate_pagination(page, page_size)

        stmt = select(Task).where(Task.is_deleted.is_(True))
        count_stmt = select(func.count(Task.id)).where(Task.is_deleted.is_(True))

        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
            count_stmt = count_stmt.where(Task.task_type == task_type)
        if status:
            stmt = stmt.where(Task.status == status)
            count_stmt = count_stmt.where(Task.status == status)

        if with_related:
            stmt = self._with_related(stmt)

        stmt = stmt.order_by(Task.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)


task_crud = CRUDTask(Task)
