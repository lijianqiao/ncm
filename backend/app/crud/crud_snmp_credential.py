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
from sqlalchemy.sql.elements import ColumnElement

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

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        dept_id: UUID | None = None,
    ) -> tuple[list[DeptSnmpCredential], int]:
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]
        if dept_id:
            conditions.append(self.model.dept_id == dept_id)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(DeptSnmpCredential.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(DeptSnmpCredential.dept))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[DeptSnmpCredential], int]:
        """获取已删除 SNMP 凭据的分页列表（回收站）。"""
        page, page_size = self._validate_pagination(page, page_size, max_size=500, default_size=20)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(True)]
        keyword_clause = self._or_ilike_contains(keyword, [self.model.description, self.model.v3_username])
        if keyword_clause is not None:
            conditions.append(keyword_clause)

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(DeptSnmpCredential.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(DeptSnmpCredential.dept))
            .where(where_clause)
            .order_by(self.model.updated_at.desc())
        )
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=500, default_size=20
        )

    async def get_deleted(self, db: AsyncSession, id: UUID) -> DeptSnmpCredential | None:
        """获取已删除的 SNMP 凭据（用于恢复或彻底删除）。"""
        query = (
            select(self.model)
            .options(selectinload(DeptSnmpCredential.dept))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(True))
        )
        result = await db.execute(query)
        return result.scalars().first()


dept_snmp_credential = CRUDDeptSnmpCredential(DeptSnmpCredential)
