"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: collect.py
@DateTime: 2026-01-09 22:40:00
@Docs: ARP/MAC 采集 API 接口 (Collection API Endpoints).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import CollectServiceDep, CurrentUser, require_permissions
from app.core.otp_notice import build_otp_required_response, is_otp_error_text
from app.core.permissions import PermissionCode
from app.schemas.collect import (
    ARPTableResponse,
    CollectBatchRequest,
    CollectDeviceRequest,
    CollectResult,
    CollectTaskStatus,
    DeviceCollectResult,
    LocateResponse,
    MACTableResponse,
)
from app.schemas.common import ResponseBase

router = APIRouter(tags=["ARP/MAC采集"])


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
    service: CollectServiceDep,
    current_user: CurrentUser,
    request: CollectDeviceRequest | None = None,
) -> ResponseBase[DeviceCollectResult]:
    """立即采集指定设备的 ARP/MAC 表。

    手动触发针对单个设备的即时数据采集。支持选择性采集 ARP、MAC 或两者。

    Args:
        device_id (UUID): 设备的主键 ID。
        service (CollectService): 采集服务依赖。
        current_user (User): 当前操作人。
        request (CollectDeviceRequest | None, optional): 采集选项，包括是否采集 ARP/MAC。默认为两者都采集。

    Returns:
        ResponseBase[DeviceCollectResult]: 包含采集结果详情的响应。
    """
    collect_arp = request.collect_arp if request else True
    collect_mac = request.collect_mac if request else True
    otp_code = request.otp_code if request else None

    result = await service.collect_device(
        device_id=device_id,
        collect_arp=collect_arp,
        collect_mac=collect_mac,
        otp_code=otp_code,
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
    service: CollectServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[CollectResult] | JSONResponse:
    """批量同步采集多台设备的 ARP/MAC 表。

    该接口会阻塞直到所有选定设备处理完毕。推荐在设备数量较少时使用。
    支持通过 request 传入 OTP 验证码以应对加固设备。

    Args:
        request (CollectBatchRequest): 包含目标设备 ID 列表和采集配置的任务请求。
        service (CollectService): 采集服务依赖。
        current_user (User): 当前操作人。

    Returns:
        ResponseBase[CollectResult]: 包含批量采集统计信息（成功/失败计数）的响应。
    """
    result = await service.batch_collect(request)

    failed_otp_device_ids = [
        str(item.device_id) for item in result.results if (not item.success) and is_otp_error_text(item.error_message)
    ]
    if failed_otp_device_ids:
        return build_otp_required_response(
            details={"otp_required": True, "failed_devices": failed_otp_device_ids},
        )

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
    """通过 Celery 提交异步批量采集任务。

    适用于大规模设备采集。接口立即返回任务 ID，客户端可通过查询接口实时获取进度。

    Args:
        request (CollectBatchRequest): 包含目标设备列表和选项。
        current_user (User): 当前操作人。

    Returns:
        ResponseBase[CollectTaskStatus]: 包含 Celery 任务 ID 的响应结构。
    """
    from app.celery.tasks.collect import batch_collect_tables

    # 提交 Celery 任务
    task = batch_collect_tables.delay(  # type: ignore[attr-defined]
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
async def get_task_status(task_id: str) -> ResponseBase[CollectTaskStatus] | JSONResponse:
    """根据任务 ID 查询 Celery 异步任务的当前状态和结果。

    如果在任务完成后调用，将返回详细的采集结果或错误信息。

    Args:
        task_id (str): Celery 任务的唯一标识符。

    Returns:
        ResponseBase[CollectTaskStatus]: 包含状态、进度及最终结果（如有）的响应。
    """
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
            failed_otp_device_ids = [
                str(item.device_id)
                for item in status.result.results
                if (not item.success) and is_otp_error_text(item.error_message)
            ]
            if failed_otp_device_ids:
                return build_otp_required_response(
                    details={"otp_required": True, "failed_devices": failed_otp_device_ids},
                )
        else:
            status.error = str(result.result)
            if is_otp_error_text(status.error):
                return build_otp_required_response(
                    message=status.error,
                    details={"otp_required": True},
                )

    return ResponseBase(data=status)


# ===== 缓存数据查询 =====


@router.get(
    "/device/{device_id}/arp",
    response_model=ResponseBase[ARPTableResponse],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="获取设备 ARP 表",
    description="获取设备缓存的 ARP 表数据。",
)
async def get_device_arp(
    device_id: UUID,
    service: CollectServiceDep,
) -> ResponseBase[ARPTableResponse]:
    """获取指定设备最近一次采集成功的 ARP 表缓存数据。

    Args:
        device_id (UUID): 设备的主键 ID。
        service (CollectService): 采集服务依赖。

    Returns:
        ResponseBase[ARPTableResponse]: 包含 ARP 条目列表及缓存时间的响应。
    """
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
async def get_device_mac(
    device_id: UUID,
    service: CollectServiceDep,
) -> ResponseBase[MACTableResponse]:
    """获取指定设备最近一次采集成功的 MAC 地址表缓存数据。

    Args:
        device_id (UUID): 设备的主键 ID。
        service (CollectService): 采集服务依赖。

    Returns:
        ResponseBase[MACTableResponse]: 包含 MAC 条目列表及缓存时间的响应。
    """
    result = await service.get_cached_mac(device_id)

    message = f"共 {result.total} 条记录"
    if result.cached_at:
        message += f"（缓存于 {result.cached_at.strftime('%Y-%m-%d %H:%M:%S')}）"
    else:
        message = "暂无缓存数据，请先执行采集"

    return ResponseBase(data=result, message=message)


# ===== IP/MAC 精准定位 =====


@router.get(
    "/locate/ip/{ip_address:path}",
    response_model=ResponseBase[LocateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="IP 地址定位",
    description="根据 IP 地址查询所在设备和端口。",
)
async def locate_by_ip(
    ip_address: str,
    service: CollectServiceDep,
) -> ResponseBase[LocateResponse]:
    """根据 IP 地址在全网 ARP 表缓存中进行精准定位。

    通过匹配 IP 地址，找到该 IP 出现的具体设备及其对应的物理接口。

    Args:
        ip_address (str): 要搜索的 IP 地址。
        service (CollectService): 采集服务依赖。

    Returns:
        ResponseBase[LocateResponse]: 包含匹配到的设备 ID、名称和端口信息的响应。
    """
    result = await service.locate_by_ip(ip_address)

    if result.total > 0:
        message = f"找到 {result.total} 条匹配记录"
    else:
        message = "未找到匹配记录，请确保已采集 ARP 数据"

    return ResponseBase(data=result, message=message)


@router.get(
    "/locate/mac/{mac_address:path}",
    response_model=ResponseBase[LocateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.COLLECT_VIEW.value]))],
    summary="MAC 地址定位",
    description="根据 MAC 地址查询所在设备和端口。",
)
async def locate_by_mac(
    mac_address: str,
    service: CollectServiceDep,
) -> ResponseBase[LocateResponse]:
    """根据 MAC 地址在全网 ARP/MAC 缓存中进行精准定位。

    系统会自动格式化输入的 MAC 地址，并搜索全库。

    Args:
        mac_address (str): 要搜索的 MAC 地址（支持多种常见格式）。
        service (CollectService): 采集服务依赖。

    Returns:
        ResponseBase[LocateResponse]: 包含匹配到的物理位置信息的响应。
    """
    result = await service.locate_by_mac(mac_address)

    if result.total > 0:
        message = f"找到 {result.total} 条匹配记录"
    else:
        message = "未找到匹配记录，请确保已采集 ARP/MAC 数据"

    return ResponseBase(data=result, message=message)
