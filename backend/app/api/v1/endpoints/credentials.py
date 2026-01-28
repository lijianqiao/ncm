"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credentials.py
@DateTime: 2026-01-09 19:35:00
@Docs: 设备分组凭据 API 接口 (Credentials API).

路由顺序规则：静态路由必须在动态路由之前定义。
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.enums import DeviceGroup
from app.core.otp_notice import build_otp_required_response
from app.core.permissions import PermissionCode
from app.features.import_export.credentials import (
    CREDENTIAL_IMPORT_COLUMN_ALIASES,
    build_credential_import_template,
    export_credentials_df,
    persist_credentials,
    validate_credentials,
)
from app.import_export import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportExportService,
    ImportPreviewResponse,
    ImportValidateResponse,
    delete_export_file,
)
from app.schemas.common import BatchOperationResult, PaginatedResponse, ResponseBase
from app.schemas.credential import (
    CredentialBatchRequest,
    DeviceGroupCredentialCreate,
    DeviceGroupCredentialResponse,
    DeviceGroupCredentialUpdate,
    OTPCacheRequest,
    OTPCacheResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
)

router = APIRouter()


# ===== 列表与创建（根路由）=====


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]],
    summary="获取凭据列表",
)
async def read_credentials(
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    dept_id: UUID | None = Query(None, description="部门筛选"),
    device_group: DeviceGroup | None = Query(None, description="设备分组筛选"),
) -> ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]:
    """查询凭据列表（分页）。"""
    credentials, total = await credential_service.get_credentials_paginated(
        page=page,
        page_size=page_size,
        dept_id=dept_id,
        device_group=device_group,
    )

    items = [credential_service.to_response(c) for c in credentials]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.post(
    "/",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="创建凭据",
)
async def create_credential(
    obj_in: DeviceGroupCredentialCreate,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_CREATE.value])),
) -> Any:
    """创建设备分组凭据。"""
    credential = await credential_service.create_credential(obj_in)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据创建成功",
    )


# ===== 静态路由（必须在动态路由之前）=====


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]],
    summary="获取回收站凭据列表",
)
async def read_recycle_bin_credentials(
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键字搜索"),
) -> ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]:
    """获取回收站凭据列表（已删除的凭据）。"""
    credentials, total = await credential_service.get_recycle_bin_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
    )

    items = [credential_service.to_response(c) for c in credentials]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.get(
    "/export",
    summary="导出分组凭据",
)
async def export_credentials(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
):
    """导出分组凭据为 CSV/XLSX 文件。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="credentials", df_fn=export_credentials_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.post(
    "/otp/cache",
    response_model=ResponseBase[OTPCacheResponse],
    summary="缓存 OTP 验证码",
)
async def cache_otp(
    request: OTPCacheRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_USE.value])),
) -> Any:
    """缓存用户手动输入的 OTP 验证码。"""
    result = await credential_service.cache_otp(request)
    return ResponseBase(data=result, message=result.message)


@router.post(
    "/otp/verify",
    response_model=ResponseBase[OTPVerifyResponse],
    summary="验证并缓存 OTP 验证码",
)
async def verify_otp(
    request: OTPVerifyRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_USE.value])),
) -> Any:
    """验证并缓存用户手动输入的 OTP 验证码。"""
    from app.core.exceptions import OTPRequiredException

    try:
        result = await credential_service.verify_and_cache_otp(request)
        return ResponseBase(data=result, message=result.message)
    except OTPRequiredException as e:
        return build_otp_required_response(e)


@router.delete(
    "/batch",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量删除凭据",
)
async def batch_delete_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量删除凭据（软删除）。"""
    result = await credential_service.batch_delete_credentials(request.ids)
    return ResponseBase(data=result)


@router.post(
    "/batch/restore",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量恢复凭据",
)
async def batch_restore_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量恢复已删除的凭据。"""
    result = await credential_service.batch_restore_credentials(request.ids)
    return ResponseBase(data=result)


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量彻底删除凭据",
)
async def batch_hard_delete_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量彻底删除凭据（硬删除，不可恢复）。"""
    result = await credential_service.batch_hard_delete_credentials(request.ids)
    return ResponseBase(data=result)


@router.get(
    "/import/template",
    summary="下载分组凭据导入模板",
)
async def download_credential_import_template(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_IMPORT.value])),
):
    """下载分组凭据批量导入模板。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.build_template(
        filename_prefix="credential_import_template", builder=build_credential_import_template
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
    summary="上传并校验分组凭据导入文件",
)
async def upload_parse_validate_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_IMPORT.value])),
    file: UploadFile = File(...),
    allow_overwrite: bool = Form(default=False),
) -> ResponseBase[ImportValidateResponse]:
    """上传并校验分组凭据导入文件。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.upload_parse_validate(
        file=file,
        column_aliases=CREDENTIAL_IMPORT_COLUMN_ALIASES,
        validate_fn=validate_credentials,
        allow_overwrite=allow_overwrite,
    )
    return ResponseBase(data=resp)


@router.get(
    "/import/preview",
    response_model=ResponseBase[ImportPreviewResponse],
    summary="预览分组凭据导入数据",
)
async def preview_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_IMPORT.value])),
    import_id: UUID = Query(..., description="导入ID"),
    checksum: str = Query(..., description="文件校验和"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    kind: str = Query("all", pattern="^(all|valid)$", description="预览类型"),
) -> ResponseBase[ImportPreviewResponse]:
    """预览分组凭据导入数据。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.preview(import_id=import_id, checksum=checksum, page=page, page_size=page_size, kind=kind)
    return ResponseBase(data=resp)


@router.post(
    "/import/commit",
    response_model=ResponseBase[ImportCommitResponse],
    summary="提交分组凭据导入",
)
async def commit_credential_import(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    body: ImportCommitRequest,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_IMPORT.value])),
) -> ResponseBase[ImportCommitResponse]:
    """提交分组凭据导入（单事务执行）。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    resp = await svc.commit(body=body, persist_fn=persist_credentials, lock_namespace="import")
    return ResponseBase(data=resp)


# ===== 动态路由（带路径参数）=====


@router.get(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="获取凭据详情",
)
async def read_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
) -> Any:
    """根据 ID 获取凭据详情。"""
    credential = await credential_service.get_credential(credential_id)
    return ResponseBase(data=credential_service.to_response(credential))


@router.put(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="更新凭据",
)
async def update_credential(
    credential_id: UUID,
    obj_in: DeviceGroupCredentialUpdate,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_UPDATE.value])),
) -> Any:
    """更新凭据信息。"""
    credential = await credential_service.update_credential(credential_id, obj_in)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据更新成功",
    )


@router.delete(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="删除凭据",
)
async def delete_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """删除凭据（软删除）。"""
    credential = await credential_service.delete_credential(credential_id)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据已删除",
    )


@router.post(
    "/{credential_id:uuid}/restore",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="恢复凭据",
)
async def restore_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """恢复已删除的凭据。"""
    credential = await credential_service.restore_credential(credential_id)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据已恢复",
    )


@router.delete(
    "/{credential_id:uuid}/hard",
    response_model=ResponseBase[dict],
    summary="彻底删除凭据",
)
async def hard_delete_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """彻底删除凭据（硬删除，不可恢复）。"""
    await credential_service.hard_delete_credential(credential_id)
    return ResponseBase(
        data={"message": "凭据已彻底删除"},
        message="凭据已彻底删除",
    )
