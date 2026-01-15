"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template_approval.py
@DateTime: 2026-01-12 00:00:00
@Docs: TemplateApprovalStep CRUD。
"""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    async def get_by_template_and_level(
        self, db: AsyncSession, *, template_id: UUID, level: int
    ) -> TemplateApprovalStep | None:
        stmt = select(TemplateApprovalStep).where(
            TemplateApprovalStep.template_id == template_id,
            TemplateApprovalStep.level == level,
            TemplateApprovalStep.is_deleted.is_(False),
        )
        return (await db.execute(stmt)).scalars().first()

    async def list_by_template(self, db: AsyncSession, *, template_id: UUID) -> list[TemplateApprovalStep]:
        stmt = (
            select(TemplateApprovalStep)
            .where(TemplateApprovalStep.template_id == template_id, TemplateApprovalStep.is_deleted.is_(False))
            .order_by(TemplateApprovalStep.level.asc())
        )
        return list((await db.execute(stmt)).scalars().all())


template_approval_crud = CRUDTemplateApprovalStep(TemplateApprovalStep)
