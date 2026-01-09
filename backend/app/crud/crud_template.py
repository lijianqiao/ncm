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

from app.crud.base import CRUDBase
from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate


class CRUDTemplate(CRUDBase[Template, TemplateCreate, TemplateUpdate]):
    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        vendor: str | None = None,
        template_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Template], int]:
        clauses = []
        if vendor:
            # PostgreSQL ARRAY contains
            clauses.append(Template.vendors.any(vendor))  # type: ignore[attr-defined]
        if template_type:
            clauses.append(Template.template_type == template_type)
        if status:
            clauses.append(Template.status == status)

        where_clause = and_(*clauses) if clauses else None

        count_stmt = select(func.count(Template.id))
        stmt = select(Template)
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
            stmt = stmt.where(where_clause)

        stmt = stmt.order_by(Template.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)

        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)

    async def get_latest_by_parent(self, db: AsyncSession, parent_id: UUID) -> Template | None:
        stmt = (
            select(Template)
            .where(Template.parent_id == parent_id)
            .order_by(Template.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()


template = CRUDTemplate(Template)

