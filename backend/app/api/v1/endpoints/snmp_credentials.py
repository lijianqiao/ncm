"""
@Author: li
@Email: li
@FileName: snmp_credentials.py
@DateTime: 2026-01-14
@Docs: 部门 SNMP 凭据 API 端点。
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.permissions import PermissionCode
from app.crud.crud_snmp_credential import dept_snmp_credential as snmp_cred_crud
from app.features.import_export.snmp_credentials import (
    SNMP_CRED_IMPORT_COLUMN_ALIASES,
    build_snmp_credential_import_template,
    export_snmp_credentials_df,
    persist_snmp_credentials,
    validate_snmp_credentials,
)
from app.import_export import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportExportService,
    ImportPreviewResponse,
    ImportValidateResponse,
    delete_export_file,
)
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.snmp_credential import (
    DeptSnmpCredentialCreate,
    DeptSnmpCredentialResponse,
    DeptSnmpCredentialUpdate,
    SnmpCredentialBatchRequest,
    SnmpCredentialBatchResult,
)
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
    records, total = await service.get_multi_paginated(page=page, page_size=page_size, dept_id=dept_id)
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
    return ResponseBase[DeptSnmpCredentialResponse](data=resp)


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


@router.delete(
    "/batch",
    response_model=ResponseBase[SnmpCredentialBatchResult],
    summary="批量删除 SNMP 凭据",
)
async def batch_delete_snmp_credentials(
    db: deps.SessionDep,
    request: SnmpCredentialBatchRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> Any:
    """批量删除 SNMP 凭据（软删除）。"""
    service = _get_service(db)
    success_count, failed_ids = await service.batch_delete(request.ids)
    await db.commit()
    return ResponseBase(
        data=SnmpCredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量删除完成，成功 {success_count} 条",
    )


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeptSnmpCredentialResponse]],
    summary="获取回收站 SNMP 凭据列表",
)
async def read_recycle_bin_snmp_credentials(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键字搜索"),
) -> ResponseBase[PaginatedResponse[DeptSnmpCredentialResponse]]:
    """获取回收站 SNMP 凭据列表（已删除的凭据）。"""
    service = _get_service(db)
    records, total = await service.get_recycle_bin_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
    )
    items = [await service.to_response(r) for r in records]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.post(
    "/{snmp_cred_id}/restore",
    response_model=ResponseBase[DeptSnmpCredentialResponse],
    summary="恢复 SNMP 凭据",
)
async def restore_snmp_credential(
    db: deps.SessionDep,
    snmp_cred_id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> Any:
    """恢复已删除的 SNMP 凭据。"""
    service = _get_service(db)
    obj = await service.restore(snmp_cred_id)
    await db.commit()
    return ResponseBase(
        data=await service.to_response(obj),
        message="SNMP 凭据已恢复",
    )


@router.post(
    "/batch/restore",
    response_model=ResponseBase[SnmpCredentialBatchResult],
    summary="批量恢复 SNMP 凭据",
)
async def batch_restore_snmp_credentials(
    db: deps.SessionDep,
    request: SnmpCredentialBatchRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> Any:
    """批量恢复已删除的 SNMP 凭据。"""
    service = _get_service(db)
    success_count, failed_ids = await service.batch_restore(request.ids)
    await db.commit()
    return ResponseBase(
        data=SnmpCredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量恢复完成，成功 {success_count} 条",
    )


@router.delete(
    "/{snmp_cred_id}/hard",
    response_model=ResponseBase[dict],
    summary="彻底删除 SNMP 凭据",
)
async def hard_delete_snmp_credential(
    db: deps.SessionDep,
    snmp_cred_id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> Any:
    """彻底删除 SNMP 凭据（硬删除，不可恢复）。"""
    service = _get_service(db)
    await service.hard_delete(snmp_cred_id)
    await db.commit()
    return ResponseBase(
        data={"message": "SNMP 凭据已彻底删除"},
        message="SNMP 凭据已彻底删除",
    )


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[SnmpCredentialBatchResult],
    summary="批量彻底删除 SNMP 凭据",
)
async def batch_hard_delete_snmp_credentials(
    db: deps.SessionDep,
    request: SnmpCredentialBatchRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_DELETE.value])),
) -> Any:
    """批量彻底删除 SNMP 凭据（硬删除，不可恢复）。"""
    service = _get_service(db)
    success_count, failed_ids = await service.batch_hard_delete(request.ids)
    await db.commit()
    return ResponseBase(
        data=SnmpCredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量彻底删除完成，成功 {success_count} 条",
    )


@router.get(
    "/export",
    summary="导出 SNMP 凭据",
)
async def export_snmp_credentials(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
):
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="snmp_credentials", df_fn=export_snmp_credentials_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.get(
    "/import/template",
    summary="下载 SNMP 凭据导入模板",
)
async def download_snmp_credential_import_template(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_IMPORT.value])),
):
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.build_template(
        filename_prefix="snmp_credential_import_template", builder=build_snmp_credential_import_template
    )
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.post(
    "/import/upload",
    response_model=ResponseBase[ImportValidateResponse],
    summary="上传并校验 SNMP 凭据导入文件",
)
async def upload_parse_validate_snmp_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_IMPORT.value])),
    file: UploadFile = File(...),
    allow_overwrite: bool = Form(default=False),
) -> ResponseBase[ImportValidateResponse]:
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.upload_parse_validate(
        file=file,
        column_aliases=SNMP_CRED_IMPORT_COLUMN_ALIASES,
        validate_fn=validate_snmp_credentials,
        allow_overwrite=allow_overwrite,
    )
    return ResponseBase(data=resp)


@router.get(
    "/import/preview",
    response_model=ResponseBase[ImportPreviewResponse],
    summary="预览 SNMP 凭据导入数据",
)
async def preview_snmp_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_IMPORT.value])),
    import_id: UUID = Query(..., description="导入ID"),
    checksum: str = Query(..., description="文件校验和"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    kind: str = Query("all", pattern="^(all|valid)$", description="预览类型"),
) -> ResponseBase[ImportPreviewResponse]:
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.preview(import_id=import_id, checksum=checksum, page=page, page_size=page_size, kind=kind)
    return ResponseBase(data=resp)


@router.post(
    "/import/commit",
    response_model=ResponseBase[ImportCommitResponse],
    summary="提交 SNMP 凭据导入",
)
async def commit_snmp_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    body: ImportCommitRequest,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SNMP_CRED_IMPORT.value])),
) -> ResponseBase[ImportCommitResponse]:
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.commit(body=body, persist_fn=persist_snmp_credentials, lock_namespace="import")
    return ResponseBase(data=resp)
