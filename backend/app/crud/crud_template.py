"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template CRUD。
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.crud.base import CRUDBase
from app.models.template import Template
from app.models.template_approval import TemplateApprovalStep
from app.schemas.template import TemplateCreate, TemplateUpdate


class CRUDTemplate(CRUDBase[Template, TemplateCreate, TemplateUpdate]):
    """模板 CRUD 操作类。"""

    @staticmethod
    def _build_template_options() -> list:
        """构建模板查询的 selectinload 配置（避免重复代码）。"""
        return [
            selectinload(Template.creator),
            selectinload(Template.approval_steps).selectinload(TemplateApprovalStep.approver),
            with_loader_criteria(
                TemplateApprovalStep,
                TemplateApprovalStep.is_deleted.is_(False),
                include_aliases=True,
            ),
        ]

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> Template | None:
        """根据 ID 获取模板（预加载关联）。"""
        return await super().get(db, id, is_deleted=is_deleted, options=options or self._build_template_options())

    async def get_latest_by_parent(self, db: AsyncSession, parent_id: UUID) -> Template | None:
        """获取父模板的最新版本。"""
        stmt = (
            select(Template)
            .where(Template.parent_id == parent_id, Template.is_deleted.is_(False))
            .order_by(Template.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()


template = CRUDTemplate(Template)
