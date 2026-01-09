"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: collect.py
@DateTime: 2026-01-09 22:40:00
@Docs: ARP/MAC 采集 API 接口 (Collection API Endpoints).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_permissions
from app.core.db import AsyncSessionLocal
from app.core.permissions import PermissionCode
from app.crud.crud_credential import credential as credential_crud
from app.crud.crud_device import device as device_crud
from app.schemas.collect import (
    ARPTableResponse,
    CollectBatchRequest,
    CollectDeviceRequest,
    CollectResult,
    CollectTaskStatus,
    DeviceCollectResult,
    MACTableResponse,
)
from app.schemas.common import ResponseBase
from app.services.collect_service import CollectService

router = APIRouter(prefix="/collect", tags=["ARP/MAC采集"])


async def get_collect_service():
    """获取采集服务实例。"""
    async with AsyncSessionLocal() as db:
        yield CollectService(db, device_crud, credential_crud)


# ===== 手动采集 =====


@router.post(
    "/device/{device_id}",
    response_model=ResponseBase[DeviceCollectResult],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_EXECUTE.value]))],
    summary="手动采集单设备",
    description="立即采集指定设备的 ARP/MAC 表。",
)
async def collect_device(
    device_id: UUID,
    current_user: CurrentUser,
    request: CollectDeviceRequest | None = None,
) -> ResponseBase[DeviceCollectResult]:
    """手动采集单设备。"""
    async with AsyncSessionLocal() as db:
        service = CollectService(db, device_crud, credential_crud)
        collect_arp = request.collect_arp if request else True
        collect_mac = request.collect_mac if request else True

        result = await service.collect_device(
            device_id=device_id,
            collect_arp=collect_arp,
            collect_mac=collect_mac,
        )

        return ResponseBase(
            data=result,
            message="采集完成" if result.success else "采集失败",
        )


@router.post(
    "/batch",
    response_model=ResponseBase[CollectResult],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_EXECUTE.value]))],
    summary="批量采集设备",
    description="批量采集多台设备的 ARP/MAC 表。",
)
async def batch_collect(
    request: CollectBatchRequest,
    current_user: CurrentUser,
) -> ResponseBase[CollectResult]:
    """批量采集设备。

    支持传入 OTP 验证码用于需要 OTP 认证的设备。
    """
    async with AsyncSessionLocal() as db:
        service = CollectService(db, device_crud, credential_crud)
        result = await service.batch_collect(request)

        return ResponseBase(
            data=result,
            message=f"批量采集完成: 成功 {result.success_count}/{result.total_devices}",
        )


@router.post(
    "/batch/async",
    response_model=ResponseBase[CollectTaskStatus],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_EXECUTE.value]))],
    summary="异步批量采集（Celery）",
    description="提交异步批量采集任务到 Celery 队列。",
)
async def batch_collect_async(
    request: CollectBatchRequest,
    current_user: CurrentUser,
) -> ResponseBase[CollectTaskStatus]:
    """异步批量采集（通过 Celery）。

    返回任务ID，可通过 /collect/task/{task_id} 查询进度。
    """
    from app.celery.tasks.collect import batch_collect_tables

    # 提交 Celery 任务
    task = batch_collect_tables.delay(
        device_ids=[str(did) for did in request.device_ids],
        collect_arp=request.collect_arp,
        collect_mac=request.collect_mac,
        otp_code=request.otp_code,
    )

    return ResponseBase(
        data=CollectTaskStatus(
            task_id=task.id,
            status="PENDING",
            progress=0,
        ),
        message="采集任务已提交",
    )


# ===== 任务状态查询 =====


@router.get(
    "/task/{task_id}",
    response_model=ResponseBase[CollectTaskStatus],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="查询采集任务状态",
    description="查询 Celery 异步采集任务的执行状态。",
)
async def get_task_status(task_id: str) -> ResponseBase[CollectTaskStatus]:
    """查询采集任务状态。"""
    from celery.result import AsyncResult

    from app.celery.app import celery_app

    result = AsyncResult(task_id, app=celery_app)

    status = CollectTaskStatus(
        task_id=task_id,
        status=result.status,
        progress=100 if result.ready() else 0,
    )

    if result.ready():
        if result.successful():
            status.result = CollectResult(**result.result)
        else:
            status.error = str(result.result)

    return ResponseBase(data=status)


# ===== 缓存数据查询 =====


@router.get(
    "/device/{device_id}/arp",
    response_model=ResponseBase[ARPTableResponse],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="获取设备 ARP 表",
    description="获取设备缓存的 ARP 表数据。",
)
async def get_device_arp(device_id: UUID) -> ResponseBase[ARPTableResponse]:
    """获取设备 ARP 表缓存。"""
    async with AsyncSessionLocal() as db:
        service = CollectService(db, device_crud, credential_crud)
        result = await service.get_cached_arp(device_id)

        message = f"共 {result.total} 条记录"
        if result.cached_at:
            message += f"（缓存于 {result.cached_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        else:
            message = "暂无缓存数据，请先执行采集"

        return ResponseBase(data=result, message=message)


@router.get(
    "/device/{device_id}/mac",
    response_model=ResponseBase[MACTableResponse],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="获取设备 MAC 表",
    description="获取设备缓存的 MAC 地址表数据。",
)
async def get_device_mac(device_id: UUID) -> ResponseBase[MACTableResponse]:
    """获取设备 MAC 表缓存。"""
    async with AsyncSessionLocal() as db:
        service = CollectService(db, device_crud, credential_crud)
        result = await service.get_cached_mac(device_id)

        message = f"共 {result.total} 条记录"
        if result.cached_at:
            message += f"（缓存于 {result.cached_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        else:
            message = "暂无缓存数据，请先执行采集"

        return ResponseBase(data=result, message=message)
