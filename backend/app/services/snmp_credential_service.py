"""
@Author: li
@Email: li
@FileName: snmp_credential_service.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据服务。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_snmp_secret
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_dept import dept as dept_crud
from app.crud.crud_snmp_credential import CRUDDeptSnmpCredential
from app.models.snmp_credential import DeptSnmpCredential
from app.schemas.snmp_credential import (
    DeptSnmpCredentialCreate,
    DeptSnmpCredentialResponse,
    DeptSnmpCredentialUpdate,
)


class SnmpCredentialService:
    def __init__(self, db: AsyncSession, snmp_cred_crud: CRUDDeptSnmpCredential):
        self.db = db
        self.snmp_cred_crud = snmp_cred_crud

    async def list(self, *, page: int = 1, page_size: int = 20, dept_id: UUID | None = None):
        return await self.snmp_cred_crud.get_multi_paginated_filtered(
            self.db,
            page=page,
            page_size=page_size,
            dept_id=dept_id,
        )

    async def get(self, *, snmp_cred_id: UUID) -> DeptSnmpCredentialResponse:
        obj = await self.snmp_cred_crud.get(self.db, id=snmp_cred_id)
        if not obj or obj.is_deleted:
            raise NotFoundException(message="SNMP 凭据不存在")
        return await self._to_response(obj)

    async def create(self, *, data: DeptSnmpCredentialCreate) -> DeptSnmpCredentialResponse:
        existing = await self.snmp_cred_crud.get_by_dept_id(self.db, dept_id=data.dept_id)
        if existing:
            raise BadRequestException(message="该部门已存在 SNMP 凭据")

        obj_data = data.model_dump(exclude_unset=True)
        community = obj_data.pop("community", None)
        if community:
            obj_data["community_encrypted"] = encrypt_snmp_secret(community)

        v3_auth_key = obj_data.pop("v3_auth_key", None)
        if v3_auth_key:
            obj_data["v3_auth_key_encrypted"] = encrypt_snmp_secret(v3_auth_key)

        v3_priv_key = obj_data.pop("v3_priv_key", None)
        if v3_priv_key:
            obj_data["v3_priv_key_encrypted"] = encrypt_snmp_secret(v3_priv_key)

        obj = DeptSnmpCredential(**obj_data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return await self._to_response(obj)

    async def update(self, *, snmp_cred_id: UUID, data: DeptSnmpCredentialUpdate) -> DeptSnmpCredentialResponse:
        obj = await self.snmp_cred_crud.get(self.db, id=snmp_cred_id)
        if not obj or obj.is_deleted:
            raise NotFoundException(message="SNMP 凭据不存在")

        update_data = data.model_dump(exclude_unset=True)
        community = update_data.pop("community", None)
        if community is not None:
            update_data["community_encrypted"] = encrypt_snmp_secret(community) if community else None

        v3_auth_key = update_data.pop("v3_auth_key", None)
        if v3_auth_key is not None:
            update_data["v3_auth_key_encrypted"] = encrypt_snmp_secret(v3_auth_key) if v3_auth_key else None

        v3_priv_key = update_data.pop("v3_priv_key", None)
        if v3_priv_key is not None:
            update_data["v3_priv_key_encrypted"] = encrypt_snmp_secret(v3_priv_key) if v3_priv_key else None

        obj = await self.snmp_cred_crud.update(self.db, db_obj=obj, obj_in=update_data)
        await self.db.flush()
        await self.db.refresh(obj)
        return await self._to_response(obj)

    async def delete(self, *, snmp_cred_id: UUID) -> None:
        obj = await self.snmp_cred_crud.remove(self.db, id=snmp_cred_id)
        if not obj:
            raise NotFoundException(message="SNMP 凭据不存在")

    async def to_response(self, obj) -> DeptSnmpCredentialResponse:
        return await self._to_response(obj)

    async def _to_response(self, obj) -> DeptSnmpCredentialResponse:
        dept_name = None
        dept = await dept_crud.get(self.db, id=obj.dept_id)
        if dept:
            dept_name = dept.name

        return DeptSnmpCredentialResponse(
            id=obj.id,
            dept_id=obj.dept_id,
            dept_name=dept_name,
            snmp_version=obj.snmp_version,
            port=obj.port,
            has_community=bool(obj.community_encrypted),
            description=obj.description,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
