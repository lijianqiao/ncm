"""
@Author: li
@Email: li
@FileName: snmp_credentials.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据 API 端点。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.permissions import PermissionCode
from app.crud.crud_snmp_credential import dept_snmp_credential as snmp_cred_crud
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.snmp_credential import DeptSnmpCredentialCreate, DeptSnmpCredentialResponse, DeptSnmpCredentialUpdate
from app.services.snmp_credential_service import SnmpCredentialService

router = APIRouter()


def _get_service(db: deps.SessionDep) -> SnmpCredentialService:
    return SnmpCredentialService(db, snmp_cred_crud)


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[DeptSnmpCredentialResponse]],
    summary="获取部门 SNMP 凭据列表",
)
async def read_snmp_credentials(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    dept_id: UUID | None = Query(None, description="部门筛选"),
) -> ResponseBase[PaginatedResponse[DeptSnmpCredentialResponse]]:
    service = _get_service(db)
    records, total = await service.list(page=page, page_size=page_size, dept_id=dept_id)
    items = [await service.to_response(r) for r in records]
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=items))


@router.post(
    "/",
    response_model=ResponseBase[DeptSnmpCredentialResponse],
    summary="创建部门 SNMP 凭据",
)
async def create_snmp_credential(
    db: deps.SessionDep,
    request: DeptSnmpCredentialCreate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_CREATE.value])),
) -> ResponseBase[DeptSnmpCredentialResponse]:
    service = _get_service(db)
    resp = await service.create(data=request)
    await db.commit()
    return ResponseBase(data=resp)


@router.put(
    "/{snmp_cred_id}",
    response_model=ResponseBase[DeptSnmpCredentialResponse],
    summary="更新部门 SNMP 凭据",
)
async def update_snmp_credential(
    db: deps.SessionDep,
    snmp_cred_id: UUID,
    request: DeptSnmpCredentialUpdate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_UPDATE.value])),
) -> ResponseBase[DeptSnmpCredentialResponse]:
    service = _get_service(db)
    resp = await service.update(snmp_cred_id=snmp_cred_id, data=request)
    await db.commit()
    return ResponseBase(data=resp)


@router.delete(
    "/{snmp_cred_id}",
    response_model=ResponseBase[dict],
    summary="删除部门 SNMP 凭据",
)
async def delete_snmp_credential(
    db: deps.SessionDep,
    snmp_cred_id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> ResponseBase[dict]:
    service = _get_service(db)
    await service.delete(snmp_cred_id=snmp_cred_id)
    await db.commit()
    return ResponseBase(data={"message": "删除成功"})
