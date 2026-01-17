"""
@Author: li
@Email: lij
@FileName: inventory_audit.py
@DateTime: 2026-01-09 21:30:00
@Docs: 资产盘点 API。
"""

from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.permissions import PermissionCode
from app.features.import_export.inventory_audit import export_inventory_audits_df
from app.import_export import ImportExportService, delete_export_file
from app.schemas.common import (
    BatchDeleteRequest,
    BatchOperationResult,
    BatchRestoreRequest,
    PaginatedResponse,
    ResponseBase,
)
from app.schemas.inventory_audit import InventoryAuditCreate, InventoryAuditResponse

router = APIRouter()


@router.post(
    "/",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="创建盘点任务（异步执行）",
)
async def create_inventory_audit(
    body: InventoryAuditCreate,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_CREATE.value])),
) -> Any:
    """提交一个资产盘点任务。

    接口会立即创建记录并触发 Celery 异步扫描，识别在线、离线、影子资产以及配置不一致设备。

    Args:
        body (InventoryAuditCreate): 盘点配置，包括名称和审计范围（网段或部门）。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 任务创建人。

    Returns:
        ResponseBase[InventoryAuditResponse]: 包含创建记录及其绑定的 Celery 任务 ID。
    """
    audit = await service.create(body, operator_id=current_user.id)

    from app.celery.tasks.inventory_audit import run_inventory_audit

    celery_result = cast(Any, run_inventory_audit).delay(audit_id=str(audit.id))  # type: ignore[attr-defined]
    audit = await service.bind_celery_task(audit.id, celery_task_id=celery_result.id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit))


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[InventoryAuditResponse]],
    summary="盘点任务列表",
)
async def list_inventory_audits(
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    status: str | None = Query(default=None, description="状态筛选"),
) -> ResponseBase[PaginatedResponse[InventoryAuditResponse]]:
    """获取所有历史和正在进行的资产盘点任务记录。

    Args:
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页限制。
        status (str | None): 任务状态过滤。

    Returns:
        ResponseBase[PaginatedResponse[InventoryAuditResponse]]: 分页盘点记录。
    """
    items, total = await service.list_paginated(page=page, page_size=page_size, status=status)
    return ResponseBase(
        data=PaginatedResponse(
            items=[InventoryAuditResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[InventoryAuditResponse]],
    summary="盘点任务回收站列表",
)
async def list_inventory_audits_recycle_bin(
    service: deps.InventoryAuditServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_RECYCLE.value])),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    status: str | None = Query(default=None, description="状态筛选"),
) -> ResponseBase[PaginatedResponse[InventoryAuditResponse]]:
    """获取已删除的盘点任务列表（回收站）。

    仅限超级管理员访问。

    Args:
        service (InventoryAuditService): 资产盘点服务。
        active_superuser (User): 超级管理员权限验证。
        page (int): 页码。
        page_size (int): 每页数量。
        status (str | None): 状态筛选。

    Returns:
        ResponseBase[PaginatedResponse[InventoryAuditResponse]]: 回收站中的盘点任务列表。
    """
    items, total = await service.list_deleted_paginated(page=page, page_size=page_size, status=status)
    return ResponseBase(
        data=PaginatedResponse(
            items=[InventoryAuditResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.delete(
    "/batch",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量删除盘点任务",
)
async def batch_delete_inventory_audits(
    request: BatchDeleteRequest,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_DELETE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量删除盘点任务（软删除）。

    Args:
        request (BatchDeleteRequest): 批量删除请求体。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果。
    """
    success_count, failed_ids = await service.batch_delete(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功删除 {success_count} 个盘点任务" if not failed_ids else "部分删除成功",
        )
    )


@router.delete(
    "/{audit_id}",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="删除盘点任务",
)
async def delete_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_DELETE.value])),
) -> ResponseBase[InventoryAuditResponse]:
    """删除盘点任务（软删除）。

    Args:
        audit_id (UUID): 盘点任务 ID。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[InventoryAuditResponse]: 被删除的盘点任务详情。
    """
    audit = await service.delete(audit_id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit), message="盘点任务删除成功")


@router.post(
    "/batch/restore",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量恢复盘点任务",
)
async def batch_restore_inventory_audits(
    request: BatchRestoreRequest,
    service: deps.InventoryAuditServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_RESTORE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量恢复盘点任务。

    仅限超级管理员访问。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体。
        service (InventoryAuditService): 资产盘点服务。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """
    success_count, failed_ids = await service.batch_restore(ids=request.ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功恢复 {success_count} 个盘点任务" if not failed_ids else "部分恢复成功",
        )
    )


@router.post(
    "/{audit_id}/restore",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="恢复已删除盘点任务",
)
async def restore_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_RESTORE.value])),
) -> ResponseBase[InventoryAuditResponse]:
    """恢复已删除的盘点任务。

    仅限超级管理员访问。

    Args:
        audit_id (UUID): 盘点任务 ID。
        service (InventoryAuditService): 资产盘点服务。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[InventoryAuditResponse]: 恢复后的盘点任务详情。
    """
    audit = await service.restore(audit_id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit), message="盘点任务恢复成功")


@router.delete(
    "/{audit_id}/hard",
    response_model=ResponseBase[dict],
    summary="彻底删除盘点任务",
)
async def hard_delete_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_DELETE.value])),
) -> ResponseBase[dict]:
    """彻底删除盘点任务（硬删除，不可恢复）。

    仅限超级管理员访问。

    Args:
        audit_id (UUID): 盘点任务 ID。
        service (InventoryAuditService): 资产盘点服务。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[dict]: 删除结果。
    """
    await service.hard_delete(audit_id)
    return ResponseBase(data={"message": "盘点任务已彻底删除"}, message="盘点任务已彻底删除")


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[BatchOperationResult],
    summary="批量彻底删除盘点任务",
)
async def batch_hard_delete_inventory_audits(
    request: BatchDeleteRequest,
    service: deps.InventoryAuditServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_DELETE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量彻底删除盘点任务（硬删除，不可恢复）。

    仅限超级管理员访问。

    Args:
        request (BatchDeleteRequest): 批量删除请求体。
        service (InventoryAuditService): 资产盘点服务。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[BatchOperationResult]: 批量删除结果。
    """
    success_count, failed_ids = await service.batch_delete(ids=request.ids, hard_delete=True)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功彻底删除 {success_count} 个盘点任务" if not failed_ids else "部分彻底删除成功",
        )
    )


@router.get(
    "/export",
    summary="导出盘点任务列表",
)
async def export_inventory_audits(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出盘点任务列表为 CSV/XLSX 文件。

    Args:
        db (Session): 数据库会话。
        current_user (User): 当前登录用户。
        fmt (str): 导出格式，csv 或 xlsx。

    Returns:
        FileResponse: 文件下载响应，后台自动清理临时文件。
    """
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="inventory_audits", df_fn=export_inventory_audits_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.get(
    "/{audit_id}",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="盘点任务详情",
)
async def get_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
) -> Any:
    """获取指定盘点任务的执行结果摘要。

    Args:
        audit_id (UUID): 盘点任务 UUID。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[InventoryAuditResponse]: 包含审计统计及分析报告的数据详情。
    """
    audit = await service.get(audit_id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit))


@router.get(
    "/{audit_id}/export",
    response_model=ResponseBase[dict],
    summary="导出盘点报告(JSON)",
)
async def export_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
) -> Any:
    """以 JSON 结构获取盘点审计的完整详单。

    Args:
        audit_id (UUID): 任务 ID。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 授权用户。

    Returns:
        ResponseBase[dict]: 包含范围、匹配明细、差异资产列表的原始数据。
    """
    audit = await service.get(audit_id)
    return ResponseBase(data={"id": str(audit.id), "name": audit.name, "scope": audit.scope, "result": audit.result})
