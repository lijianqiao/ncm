"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backups.py
@DateTime: 2026-01-09 21:00:00
@Docs: 配置备份 API 接口 (Backup API Endpoints).
"""

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import BackupServiceDep, CurrentUser, require_permissions
from app.core.enums import BackupType
from app.core.permissions import PermissionCode
from app.schemas.backup import (
    BackupBatchDeleteRequest,
    BackupBatchDeleteResult,
    BackupBatchHardDeleteRequest,
    BackupBatchRequest,
    BackupBatchRestoreRequest,
    BackupBatchRestoreResult,
    BackupBatchResult,
    BackupContentResponse,
    BackupDeviceRequest,
    BackupListQuery,
    BackupResponse,
    BackupTaskStatus,
)
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.device import DeviceResponse

router = APIRouter(tags=["配置备份"])


def _format_operator_display(user: object | None) -> str | None:
    """将用户对象格式化为 昵称(用户名) 的展示字符串。"""

    if not user:
        return None

    username = getattr(user, "username", None)
    nickname = getattr(user, "nickname", None)

    if not username:
        return None

    if nickname:
        return f"{nickname}({username})"
    return str(username)


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
    page_size: int = Query(default=20, ge=1, le=500, description="每页数量"),
    device_id: UUID | None = Query(default=None, description="设备ID筛选"),
    backup_type: BackupType | None = Query(default=None, description="备份类型筛选"),
) -> ResponseBase[PaginatedResponse[BackupResponse]]:
    """获取分页过滤的配置备份列表。

    Args:
        service (BackupService): 备份服务依赖。
        page (int): 当前页码。
        page_size (int): 每页大小。
        device_id (UUID | None): 按设备 ID 过滤。
        backup_type (BackupType | None): 按备份类型（手动/自动）过滤。

    Returns:
        ResponseBase[PaginatedResponse[BackupResponse]]: 包含备份记录的分页列表。
    """
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
            operator_id=_format_operator_display(backup.operator),
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            device=DeviceResponse.model_validate(backup.device) if backup.device else None,
            content=backup.content,
            content_path=backup.content_path,
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


@router.get(
    "/recycle",
    response_model=ResponseBase[PaginatedResponse[BackupResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_RECYCLE_LIST.value]))],
    summary="获取回收站备份列表",
    description="获取已软删除的备份列表。",
)
async def get_recycle_backups(
    service: BackupServiceDep,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=500, description="每页数量"),
    device_id: UUID | None = Query(default=None, description="设备ID筛选"),
    backup_type: BackupType | None = Query(default=None, description="备份类型筛选"),
) -> ResponseBase[PaginatedResponse[BackupResponse]]:
    query = BackupListQuery(
        page=page,
        page_size=page_size,
        device_id=device_id,
        backup_type=backup_type,
    )
    items, total = await service.get_recycle_backups_paginated(query)

    backup_responses = []
    for backup in items:
        backup_responses.append(
            BackupResponse(
                id=backup.id,
                device_id=backup.device_id,
                backup_type=backup.backup_type,
                status=backup.status,
                content_size=backup.content_size,
                md5_hash=backup.md5_hash,
                error_message=backup.error_message,
                operator_id=_format_operator_display(backup.operator),
                created_at=backup.created_at,
                updated_at=backup.updated_at,
                device=DeviceResponse.model_validate(backup.device) if backup.device else None,
                content=backup.content,
                content_path=backup.content_path,
            )
        )

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
    """根据 ID 获取单个备份记录的详细信息。

    Args:
        backup_id (UUID): 备份记录 ID。
        service (BackupService): 备份服务依赖。

    Returns:
        ResponseBase[BackupResponse]: 备份详情响应对象。
    """
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
            operator_id=_format_operator_display(backup.operator),
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            device=DeviceResponse.model_validate(backup.device) if backup.device else None,
            content=backup.content,
            content_path=backup.content_path,
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
    """获取指定备份记录的完整配置文件内容。

    Args:
        backup_id (UUID): 备份记录 ID。
        service (BackupService): 备份服务依赖。

    Returns:
        ResponseBase[BackupContentResponse]: 包含配置文本内容的响应。
    """
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
    """立即为指定设备创建一个异步备份任务或同步执行。

    Args:
        device_id (UUID): 设备 ID。
        service (BackupService): 备份服务依赖。
        current_user (User): 操作者。
        request (BackupDeviceRequest | None): 备份策略可选参数。

    Returns:
        ResponseBase[BackupResponse]: 生成的备份任务/记录信息。
    """
    backup_type = request.backup_type if request else BackupType.MANUAL
    otp_code = request.otp_code if request else None

    backup = await service.backup_single_device(
        device_id=device_id,
        backup_type=backup_type,
        operator_id=current_user.id,
        otp_code=otp_code,
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
            operator_id=_format_operator_display(current_user),
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            device=DeviceResponse.model_validate(backup.device) if backup.device else None,
            content=backup.content,
            content_path=backup.content_path,
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
    """启动一个针对多台设备的批量备份任务。

    支持断点续传场景。

    Args:
        request (BackupBatchRequest): 包含设备列表或标签，以及续传信息。
        service (BackupService): 备份服务依赖。
        current_user (User): 操作者。

    Returns:
        ResponseBase[BackupBatchResult]: 包含提交的任务 ID 和设备总量统计。
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
    """根据任务 ID 查询后台异步任务的处理状态和进度。

    Args:
        task_id (str): Celery 任务 ID。
        service (BackupService): 备份服务依赖。

    Returns:
        ResponseBase[BackupTaskStatus]: 包含任务状态、进度、成功/失败数量的对象。
    """
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
    """检索指定设备最后一次成功的配置备份记录。

    Args:
        device_id (UUID): 设备 ID。
        service (BackupService): 备份服务依赖。

    Returns:
        ResponseBase[BackupResponse | None]: 最新备份详情，若无则 data 为 None。
    """
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
            operator_id=_format_operator_display(backup.operator),
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            device=DeviceResponse.model_validate(backup.device) if backup.device else None,
            content=backup.content,
            content_path=backup.content_path,
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
    page_size: int = Query(default=20, ge=1, le=500, description="每页数量"),
) -> ResponseBase[PaginatedResponse[BackupResponse]]:
    """分页获取单个设备的全部备份记录历史。

    Args:
        device_id (UUID): 设备 ID。
        service (BackupService): 备份服务依赖。
        page (int): 页码。
        page_size (int): 每页数量。

    Returns:
        ResponseBase[PaginatedResponse[BackupResponse]]: 历史记录列表。
    """
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
            operator_id=_format_operator_display(backup.operator),
            created_at=backup.created_at,
            updated_at=backup.updated_at,
            device=DeviceResponse.model_validate(backup.device) if backup.device else None,
            content=backup.content,
            content_path=backup.content_path,
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


# ===== 下载备份配置 =====


@router.get(
    "/{backup_id}/download",
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_LIST.value]))],
    summary="下载备份配置文件",
    description="将备份配置内容导出为文件下载。",
)
async def download_backup_content(
    backup_id: UUID,
    service: BackupServiceDep,
) -> StreamingResponse:
    """下载指定备份记录的内容为 txt 文件。

    Args:
        backup_id (UUID): 备份记录 ID。
        service (BackupService): 备份服务依赖。

    Returns:
        StreamingResponse: 包含配置文件内容的 HTTP 流响应。
    """
    # 获取备份信息
    backup = await service.get_backup(backup_id)
    content = await service.get_backup_content(backup_id)

    # 构建文件名
    device_name = backup.device.name if backup.device else "unknown"
    backup_time = backup.created_at.strftime("%Y%m%d_%H%M%S")
    filename = f"{device_name}_{backup_time}.txt"

    # 创建流式响应
    content_bytes = content.encode("utf-8")
    stream = BytesIO(content_bytes)

    return StreamingResponse(
        stream,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content_bytes)),
        },
    )


# ===== 删除备份 =====


@router.delete(
    "/{backup_id}",
    response_model=ResponseBase[dict],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_DELETE.value]))],
    summary="删除备份",
    description="软删除指定的备份记录。",
)
async def delete_backup(
    backup_id: UUID,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[dict]:
    """标记删除指定的备份记录。

    Args:
        backup_id (UUID): 备份记录 ID。
        service (BackupService): 备份服务依赖。
        current_user (User): 操作者。

    Returns:
        ResponseBase[dict]: 包含被删除 ID 的确认对象。
    """
    await service.delete_backup(backup_id)

    return ResponseBase(
        data={"id": str(backup_id), "deleted": True},
        message="备份已删除",
    )


@router.post(
    "/batch-delete",
    response_model=ResponseBase[BackupBatchDeleteResult],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_BATCH_DELETE.value]))],
    summary="批量删除备份",
    description="批量软删除备份记录（会尽力清理对象存储）。",
)
async def delete_backups_batch(
    request: BackupBatchDeleteRequest,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[BackupBatchDeleteResult]:
    result = await service.delete_backups_batch(request.backup_ids)

    return ResponseBase(
        data=result,
        message=f"批量删除完成: 成功 {result.success_count}, 失败 {len(result.failed_ids)}",
    )


@router.post(
    "/batch-restore",
    response_model=ResponseBase[BackupBatchRestoreResult],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_BATCH_RESTORE.value]))],
    summary="批量恢复备份",
    description="批量恢复回收站中的备份记录。",
)
async def restore_backups_batch(
    request: BackupBatchRestoreRequest,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[BackupBatchRestoreResult]:
    result = await service.restore_backups_batch(request.backup_ids)
    return ResponseBase(
        data=result,
        message=f"批量恢复完成: 成功 {result.success_count}, 失败 {len(result.failed_ids)}",
    )


@router.post(
    "/batch-hard-delete",
    response_model=ResponseBase[BackupBatchDeleteResult],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_BATCH_HARD_DELETE.value]))],
    summary="批量硬删除备份",
    description="批量硬删除备份（物理删除，会尽力清理对象存储）。",
)
async def hard_delete_backups_batch(
    request: BackupBatchHardDeleteRequest,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[BackupBatchDeleteResult]:
    result = await service.delete_backups_batch(request.backup_ids, hard_delete=True)
    return ResponseBase(
        data=result,
        message=f"批量硬删除完成: 成功 {result.success_count}, 失败 {len(result.failed_ids)}",
    )


@router.post(
    "/{backup_id}/restore",
    response_model=ResponseBase[dict],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_RESTORE.value]))],
    summary="恢复备份",
    description="恢复回收站中的备份记录。",
)
async def restore_backup(
    backup_id: UUID,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[dict]:
    await service.restore_backup(backup_id)
    return ResponseBase(data={"id": str(backup_id), "restored": True}, message="备份已恢复")


@router.delete(
    "/{backup_id}/hard",
    response_model=ResponseBase[dict],
    dependencies=[Depends(require_permissions([PermissionCode.BACKUP_HARD_DELETE.value]))],
    summary="硬删除备份",
    description="硬删除备份记录（物理删除，会尽力清理对象存储）。",
)
async def hard_delete_backup(
    backup_id: UUID,
    service: BackupServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[dict]:
    await service.delete_backup(backup_id, hard_delete=True)
    return ResponseBase(data={"id": str(backup_id), "hard_deleted": True}, message="备份已硬删除")
