"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-10 00:10:00
@Docs: 设备发现 API 端点 (Discovery Endpoints).

提供网络扫描、发现记录管理、CMDB 比对等功能。
"""

from typing import Any, cast
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    CurrentUser,
    ScanServiceDep,
    SessionDep,
    require_permissions,
)
from app.celery.tasks.discovery import compare_cmdb, scan_subnet, scan_subnets_batch
from app.core.enums import DiscoveryStatus
from app.core.exceptions import NotFoundException
from app.core.permissions import PermissionCode
from app.crud.crud_discovery import discovery_crud
from app.schemas.common import PaginatedResponse
from app.schemas.discovery import (
    AdoptDeviceRequest,
    DiscoveryResponse,
    OfflineDevice,
    ScanRequest,
    ScanResult,
    ScanTaskStatus,
)

router = APIRouter(prefix="/discovery", tags=["设备发现"])


# ===== 扫描相关 =====


@router.post(
    "/scan",
    summary="触发网络扫描",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def trigger_scan(
    request: ScanRequest,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """
    触发网络扫描任务。

    - 支持 Nmap (详细扫描) 和 Masscan (快速扫描)
    - async_mode=True 时返回任务ID，可通过 /scan/task/{task_id} 查询状态
    - async_mode=False 时同步执行并返回结果 (仅适用于小范围扫描)
    """
    if request.async_mode:
        # 异步执行
        if len(request.subnets) == 1:
            task = cast(Any, scan_subnet).delay(
                subnet=request.subnets[0],
                scan_type=request.scan_type,
                ports=request.ports,
            )
        else:
            task = cast(Any, scan_subnets_batch).delay(
                subnets=request.subnets,
                scan_type=request.scan_type,
                ports=request.ports,
            )
        return {
            "task_id": task.id,
            "status": "pending",
            "message": "扫描任务已提交",
        }
    else:
        # 同步执行 (仅第一个网段)
        if not request.subnets:
            return {"error": "请提供至少一个网段"}

        result = cast(Any, scan_subnet).apply(args=[request.subnets[0], request.scan_type, request.ports])
        return result.get()


@router.get(
    "/scan/task/{task_id}",
    summary="查询扫描任务状态",
    response_model=ScanTaskStatus,
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def get_scan_task_status(task_id: str) -> ScanTaskStatus:
    """查询扫描任务的执行状态和结果。"""
    result = AsyncResult(task_id)

    status = ScanTaskStatus(
        task_id=task_id,
        status=result.status,
    )

    if result.ready():
        if result.successful():
            task_result = result.get()
            status.result = ScanResult.model_validate(task_result)
        else:
            status.error = str(result.result)

    return status


# ===== 发现记录管理 =====


@router.get(
    "/",
    summary="获取发现记录列表",
    response_model=PaginatedResponse[DiscoveryResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_discoveries(
    db: SessionDep,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: DiscoveryStatus | None = Query(None, description="状态筛选"),
    keyword: str | None = Query(None, description="关键词搜索"),
    scan_source: str | None = Query(None, description="扫描来源"),
) -> PaginatedResponse[DiscoveryResponse]:
    """获取发现记录分页列表，支持筛选。"""
    items, total = await discovery_crud.get_multi_paginated_filtered(
        db,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
        scan_source=scan_source,
    )

    # 转换为响应格式
    responses = []
    for item in items:
        response = DiscoveryResponse(
            id=item.id,
            ip_address=item.ip_address,
            mac_address=item.mac_address,
            vendor=item.vendor,
            device_type=item.device_type,
            hostname=item.hostname,
            os_info=item.os_info,
            open_ports=item.open_ports,
            ssh_banner=item.ssh_banner,
            first_seen_at=item.first_seen_at,
            last_seen_at=item.last_seen_at,
            offline_days=item.offline_days,
            status=item.status,
            matched_device_id=item.matched_device_id,
            scan_source=item.scan_source,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

        # 添加匹配设备信息
        if item.matched_device:
            response.matched_device_name = item.matched_device.name
            response.matched_device_ip = item.matched_device.ip_address

        responses.append(response)

    return PaginatedResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{discovery_id}",
    summary="获取发现记录详情",
    response_model=DiscoveryResponse,
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def get_discovery(
    db: SessionDep,
    discovery_id: UUID,
) -> DiscoveryResponse:
    """获取单个发现记录的详细信息。"""
    item = await discovery_crud.get(db, id=discovery_id)
    if not item:
        raise NotFoundException(message="发现记录不存在")

    response = DiscoveryResponse(
        id=item.id,
        ip_address=item.ip_address,
        mac_address=item.mac_address,
        vendor=item.vendor,
        device_type=item.device_type,
        hostname=item.hostname,
        os_info=item.os_info,
        open_ports=item.open_ports,
        ssh_banner=item.ssh_banner,
        first_seen_at=item.first_seen_at,
        last_seen_at=item.last_seen_at,
        offline_days=item.offline_days,
        status=item.status,
        matched_device_id=item.matched_device_id,
        scan_source=item.scan_source,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

    if item.matched_device:
        response.matched_device_name = item.matched_device.name
        response.matched_device_ip = item.matched_device.ip_address

    return response


@router.delete(
    "/{discovery_id}",
    summary="删除发现记录",
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_DELETE.value]))],
)
async def delete_discovery(
    db: SessionDep,
    discovery_id: UUID,
    current_user: CurrentUser,
) -> dict[str, str]:
    """删除发现记录 (软删除)。"""
    result = await discovery_crud.remove(db, id=discovery_id)
    if not result:
        raise NotFoundException(message="发现记录不存在")

    await db.commit()
    return {"message": "删除成功"}


# ===== 设备纳管 =====


@router.post(
    "/{discovery_id}/adopt",
    summary="纳管设备",
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_ADOPT.value]))],
)
async def adopt_device(
    db: SessionDep,
    discovery_id: UUID,
    request: AdoptDeviceRequest,
    scan_service: ScanServiceDep,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """
    将发现记录纳管为正式设备。

    - 自动创建 Device 记录
    - 更新发现记录状态为 MATCHED
    """
    device = await scan_service.adopt_device(
        db,
        discovery_id=discovery_id,
        name=request.name,
        vendor=request.vendor,
        device_group=request.device_group,
        dept_id=request.dept_id,
        username=request.username,
        password=request.password,
    )

    if not device:
        raise NotFoundException(message="发现记录不存在")

    await db.commit()

    return {
        "message": "设备纳管成功",
        "device_id": str(device.id),
        "device_name": device.name,
    }


# ===== 影子资产和离线设备 =====


@router.get(
    "/shadow",
    summary="获取影子资产列表",
    response_model=PaginatedResponse[DiscoveryResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_shadow_assets(
    db: SessionDep,
    scan_service: ScanServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[DiscoveryResponse]:
    """获取影子资产列表 (未在 CMDB 中的发现设备)。"""
    items, total = await scan_service.get_shadow_assets(db, page=page, page_size=page_size)

    responses = [
        DiscoveryResponse(
            id=item.id,
            ip_address=item.ip_address,
            mac_address=item.mac_address,
            vendor=item.vendor,
            device_type=item.device_type,
            hostname=item.hostname,
            os_info=item.os_info,
            open_ports=item.open_ports,
            ssh_banner=item.ssh_banner,
            first_seen_at=item.first_seen_at,
            last_seen_at=item.last_seen_at,
            offline_days=item.offline_days,
            status=item.status,
            matched_device_id=item.matched_device_id,
            scan_source=item.scan_source,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]

    return PaginatedResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/offline",
    summary="获取离线设备列表",
    response_model=list[OfflineDevice],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_offline_devices(
    db: SessionDep,
    scan_service: ScanServiceDep,
    days_threshold: int = Query(7, ge=1, description="离线天数阈值"),
) -> list[OfflineDevice]:
    """获取离线设备列表 (CMDB 中存在但长时间未扫描到)。"""
    return await scan_service.detect_offline_devices(db, days_threshold=days_threshold)


# ===== CMDB 比对 =====


@router.post(
    "/compare",
    summary="执行 CMDB 比对",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def trigger_cmdb_compare(
    current_user: CurrentUser,
    async_mode: bool = Query(True, description="是否异步执行"),
) -> dict[str, Any]:
    """
    将发现记录与 CMDB 比对。

    - 识别影子资产 (未在 CMDB 中)
    - 检测离线设备 (CMDB 中存在但未扫描到)
    """
    if async_mode:
        task = cast(Any, compare_cmdb).delay()
        return {
            "task_id": task.id,
            "status": "pending",
            "message": "CMDB 比对任务已提交",
        }
    else:
        result = cast(Any, compare_cmdb).apply()
        return result.get()
