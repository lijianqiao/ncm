"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template CRUD。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy.sql.elements import ColumnElement

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

    async def get(self, db: AsyncSession, *, id: UUID) -> Template | None:  # type: ignore[override]
        """根据 ID 获取模板（预加载关联）。"""
        stmt = (
            select(Template)
            .options(*self._build_template_options())
            .where(Template.id == id, Template.is_deleted.is_(False))
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
        """获取模板分页列表（支持筛选）。"""
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [Template.is_deleted.is_(False)]
        if vendor:
            conditions.append(Template.vendors.contains([vendor]))  # type: ignore[attr-defined]
        if template_type:
            conditions.append(Template.template_type == template_type)
        if status:
            conditions.append(Template.status == status)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(Template.id)).where(where_clause)
        stmt = (
            select(Template)
            .options(*self._build_template_options())
            .where(where_clause)
            .order_by(Template.updated_at.desc())
        )

        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

    async def get_latest_by_parent(self, db: AsyncSession, parent_id: UUID) -> Template | None:
        """获取父模板的最新版本。"""
        stmt = (
            select(Template)
            .where(Template.parent_id == parent_id, Template.is_deleted.is_(False))
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
            .options(*self._build_template_options())
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
            .options(*self._build_template_options())
            .where(Template.id == id, Template.is_deleted.is_(True))
        )
        return (await db.execute(stmt)).scalars().first()


template = CRUDTemplate(Template)
