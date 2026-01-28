"""
@Author: li
@Email: li
@FileName: crud_snmp_credential.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

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



dept_snmp_credential = CRUDDeptSnmpCredential(DeptSnmpCredential)
