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

from app.crud.base import CRUDBase
from app.models.task import Task


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
    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        task_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Task], int]:
        stmt = select(Task)
        count_stmt = select(func.count(Task.id))

        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
            count_stmt = count_stmt.where(Task.task_type == task_type)
        if status:
            stmt = stmt.where(Task.status == status)
            count_stmt = count_stmt.where(Task.status == status)

        stmt = stmt.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)


task_crud = CRUDTask(Task)
