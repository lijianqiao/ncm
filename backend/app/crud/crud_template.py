"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template CRUD。
"""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy.sql.elements import ColumnElement

from app.crud.base import CRUDBase
from app.models.template import Template
from app.models.template_approval import TemplateApprovalStep
from app.schemas.template import TemplateCreate, TemplateUpdate


class CRUDTemplate(CRUDBase[Template, TemplateCreate, TemplateUpdate]):
    async def get(self, db: AsyncSession, *, id: UUID) -> Template | None:  # type: ignore[override]
        stmt = (
            select(Template)
            .options(
                selectinload(Template.creator),
                selectinload(Template.approval_steps).selectinload(TemplateApprovalStep.approver),
                with_loader_criteria(
                    TemplateApprovalStep,
                    TemplateApprovalStep.is_deleted.is_(False),
                    include_aliases=True,
                ),
            )
            .where(Template.id == id)
            .where(Template.is_deleted.is_(False))
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        vendor: str | None = None,
        template_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Template], int]:
        page, page_size = self._validate_pagination(page, page_size)

        clauses: list[ColumnElement[bool]] = [Template.is_deleted.is_(False)]
        if vendor:
            clauses.append(Template.vendors.contains([vendor]))  # type: ignore[attr-defined]
        if template_type:
            clauses.append(Template.template_type == template_type)
        if status:
            clauses.append(Template.status == status)

        where_clause = and_(*clauses)

        count_stmt = select(func.count(Template.id)).where(where_clause)
        stmt = (
            select(Template)
            .options(
                selectinload(Template.creator),
                selectinload(Template.approval_steps).selectinload(TemplateApprovalStep.approver),
                with_loader_criteria(
                    TemplateApprovalStep,
                    TemplateApprovalStep.is_deleted.is_(False),
                    include_aliases=True,
                ),
            )
            .where(where_clause)
        )

        stmt = stmt.order_by(Template.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)

        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)

    async def get_latest_by_parent(self, db: AsyncSession, parent_id: UUID) -> Template | None:
        stmt = (
            select(Template)
            .where(Template.parent_id == parent_id)
            .where(Template.is_deleted.is_(False))
            .order_by(Template.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[Template], int]:
        """获取已删除模板的分页列表（回收站）。"""
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [Template.is_deleted.is_(True)]
        keyword_clause = self._or_ilike_contains(keyword, [Template.name, Template.description])
        if keyword_clause is not None:
            conditions.append(keyword_clause)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(Template.id)).where(where_clause)
        stmt = (
            select(Template)
            .options(
                selectinload(Template.creator),
                selectinload(Template.approval_steps).selectinload(TemplateApprovalStep.approver),
                with_loader_criteria(
                    TemplateApprovalStep,
                    TemplateApprovalStep.is_deleted.is_(False),
                    include_aliases=True,
                ),
            )
            .where(where_clause)
            .order_by(Template.updated_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

    async def get_deleted(self, db: AsyncSession, id: UUID) -> Template | None:
        """获取已删除的模板（用于恢复或彻底删除）。"""
        stmt = (
            select(Template)
            .options(
                selectinload(Template.creator),
                selectinload(Template.approval_steps).selectinload(TemplateApprovalStep.approver),
                with_loader_criteria(
                    TemplateApprovalStep,
                    TemplateApprovalStep.is_deleted.is_(False),
                    include_aliases=True,
                ),
            )
            .where(Template.id == id)
            .where(Template.is_deleted.is_(True))
        )
        return (await db.execute(stmt)).scalars().first()


template = CRUDTemplate(Template)
