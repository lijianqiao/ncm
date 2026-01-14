"""
@Author: li
@Email: li
@FileName: crud_snmp_credential.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.snmp_credential import DeptSnmpCredential
from app.schemas.snmp_credential import DeptSnmpCredentialCreate, DeptSnmpCredentialUpdate


class CRUDDeptSnmpCredential(CRUDBase[DeptSnmpCredential, DeptSnmpCredentialCreate, DeptSnmpCredentialUpdate]):
    async def get_by_dept_id(self, db: AsyncSession, *, dept_id: UUID) -> DeptSnmpCredential | None:
        query = select(self.model).where(
            and_(
                self.model.dept_id == dept_id,
                self.model.is_deleted.is_(False),
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        dept_id: UUID | None = None,
    ) -> tuple[list[DeptSnmpCredential], int]:
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        base_query = select(self.model).where(self.model.is_deleted.is_(False))
        if dept_id:
            base_query = base_query.where(self.model.dept_id == dept_id)

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(DeptSnmpCredential.dept))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())
        return items, total


dept_snmp_credential = CRUDDeptSnmpCredential(DeptSnmpCredential)
