"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backups.py
@DateTime: 2026-01-09 21:00:00
@Docs: 配置备份 API 接口 (Backup API Endpoints).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import BackupServiceDep, CurrentUser, require_permissions
from app.core.enums import BackupType
from app.core.permissions import PermissionCode
from app.schemas.backup import (
    BackupBatchRequest,
    BackupBatchResult,
    BackupContentResponse,
    BackupDeviceRequest,
    BackupListQuery,
    BackupResponse,
    BackupTaskStatus,
)
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter(prefix="/backups", tags=["配置备份"])


# ===== 备份列表 =====


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[BackupResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="获取备份列表",
    description="获取分页过滤的配置备份列表。",
)
async def get_backups(
    service: BackupServiceDep,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    device_id: UUID | None = Query(default=None, description="设备ID筛选"),
    backup_type: BackupType | None = Query(default=None, description="备份类型筛选"),
) -> ResponseBase[PaginatedResponse[BackupResponse]]:
    """获取备份列表。"""
    query = BackupListQuery(
        page=page,
        page_size=page_size,
        device_id=device_id,
        backup_type=backup_type,
    )
    items, total = await service.get_backups_paginated(query)

    # 构建响应
    backup_responses = []
    for backup in items:
        resp = BackupResponse(
            id=backup.id,
            device_id=backup.device_id,
            backup_type=backup.backup_type,
            status=backup.status,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
            error_message=backup.error_message,
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            has_content=bool(backup.content or backup.content_path),
        )
        backup_responses.append(resp)

    return ResponseBase(
        data=PaginatedResponse(
            items=backup_responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


# ===== 备份详情 =====


@router.get(
    "/{backup_id}",
    response_model=ResponseBase[BackupResponse],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="获取备份详情",
    description="根据 ID 获取备份详情。",
)
async def get_backup(
    backup_id: UUID,
    service: BackupServiceDep,
) -> ResponseBase[BackupResponse]:
    """获取备份详情。"""
    backup = await service.get_backup(backup_id)

    return ResponseBase(
        data=BackupResponse(
            id=backup.id,
            device_id=backup.device_id,
            backup_type=backup.backup_type,
            status=backup.status,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
            error_message=backup.error_message,
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            has_content=bool(backup.content or backup.content_path),
        )
    )


# ===== 获取备份配置内容 =====


@router.get(
    "/{backup_id}/content",
    response_model=ResponseBase[BackupContentResponse],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="获取备份配置内容",
    description="获取备份的完整配置内容。",
)
async def get_backup_content(
    backup_id: UUID,
    service: BackupServiceDep,
) -> ResponseBase[BackupContentResponse]:
    """获取备份配置内容。"""
    backup = await service.get_backup(backup_id)
    content = await service.get_backup_content(backup_id)

    return ResponseBase(
        data=BackupContentResponse(
            id=backup.id,
            device_id=backup.device_id,
            content=content,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
        )
    )


# ===== 单设备手动备份 =====


@router.post(
    "/device/{device_id}",
    response_model=ResponseBase[BackupResponse],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_CREATE.value]))],
    summary="手动备份单设备",
    description="立即备份指定设备的配置。",
)
async def backup_device(
    device_id: UUID,
    service: BackupServiceDep,
    current_user: CurrentUser,
    request: BackupDeviceRequest | None = None,
) -> ResponseBase[BackupResponse]:
    """手动备份单设备。"""
    backup_type = request.backup_type if request else BackupType.MANUAL

    backup = await service.backup_single_device(
        device_id=device_id,
        backup_type=backup_type,
        operator_id=current_user.id,
    )

    return ResponseBase(
        data=BackupResponse(
            id=backup.id,
            device_id=backup.device_id,
            backup_type=backup.backup_type,
            status=backup.status,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
            error_message=backup.error_message,
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            has_content=bool(backup.content or backup.content_path),
        ),
        message="备份任务已完成",
    )


# ===== 批量备份 =====


@router.post(
    "/batch",
    response_model=ResponseBase[BackupBatchResult],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_CREATE.value]))],
    summary="批量备份设备",
    description="批量备份多台设备配置（支持断点续传）。",
)
async def backup_devices_batch(
    request: BackupBatchRequest,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[BackupBatchResult]:
    """批量备份设备。

    支持断点续传：
    - 如果之前的任务因 OTP 过期中断，可以传入 `resume_task_id` 和 `skip_device_ids`
    - 服务会跳过已成功的设备，继续备份剩余设备
    """
    result = await service.backup_devices_batch(
        request=request,
        operator_id=current_user.id,
    )

    return ResponseBase(
        data=result,
        message=f"批量备份任务已提交，共 {result.total_devices} 台设备",
    )


# ===== 查询任务状态 =====


@router.get(
    "/task/{task_id}",
    response_model=ResponseBase[BackupTaskStatus],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="查询备份任务状态",
    description="查询 Celery 异步备份任务的执行状态。",
)
async def get_backup_task_status(
    task_id: str,
    service: BackupServiceDep,
) -> ResponseBase[BackupTaskStatus]:
    """查询备份任务状态。"""
    status = await service.get_task_status(task_id)

    return ResponseBase(data=status)


# ===== 获取设备最新备份 =====


@router.get(
    "/device/{device_id}/latest",
    response_model=ResponseBase[BackupResponse | None],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="获取设备最新备份",
    description="获取指定设备的最新成功备份。",
)
async def get_device_latest_backup(
    device_id: UUID,
    service: BackupServiceDep,
) -> ResponseBase[BackupResponse | None]:
    """获取设备最新备份。"""
    backup = await service.get_device_latest_backup(device_id)

    if not backup:
        return ResponseBase(data=None, message="该设备暂无备份记录")

    return ResponseBase(
        data=BackupResponse(
            id=backup.id,
            device_id=backup.device_id,
            backup_type=backup.backup_type,
            status=backup.status,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
            error_message=backup.error_message,
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            has_content=bool(backup.content or backup.content_path),
        )
    )


# ===== 获取设备备份历史 =====


@router.get(
    "/device/{device_id}/history",
    response_model=ResponseBase[PaginatedResponse[BackupResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="获取设备备份历史",
    description="获取指定设备的备份历史列表。",
)
async def get_device_backup_history(
    device_id: UUID,
    service: BackupServiceDep,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> ResponseBase[PaginatedResponse[BackupResponse]]:
    """获取设备备份历史。"""
    items, total = await service.get_device_backups(
        device_id=device_id,
        page=page,
        page_size=page_size,
    )

    backup_responses = [
        BackupResponse(
            id=backup.id,
            device_id=backup.device_id,
            backup_type=backup.backup_type,
            status=backup.status,
            content_size=backup.content_size,
            md5_hash=backup.md5_hash,
            error_message=backup.error_message,
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            has_content=bool(backup.content or backup.content_path),
        )
        for backup in items
    ]

    return ResponseBase(
        data=PaginatedResponse(
            items=backup_responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )
