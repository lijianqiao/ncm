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
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.discovery import (
    AdoptDeviceRequest,
    AdoptResponse,
    DeleteResponse,
    DiscoveryResponse,
    OfflineDevice,
    ScanBatchResult,
    ScanRequest,
    ScanResult,
    ScanTaskResponse,
    ScanTaskStatus,
)

router = APIRouter(tags=["设备发现"])


# ===== 扫描相关 =====


@router.post(
    "/scan",
    summary="触发网络扫描",
    response_model=ResponseBase[ScanTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def trigger_scan(
    request: ScanRequest,
    current_user: CurrentUser,
) -> ResponseBase[ScanTaskResponse]:
    """触发针对特定网段的网络扫描任务。

    通过 Nmap 或 Masscan 发现网络中的在线资产，并识别其开放端口及服务横幅。

    Args:
        request (ScanRequest): 包含网段、扫描类型、端口、扫描模式（同步/异步）的请求。
        current_user (CurrentUser): 当前操作人。

    Returns:
        ResponseBase[ScanTaskResponse]: 包含 task_id 的响应。
    """
    if request.async_mode:
        # 异步执行
        if len(request.subnets) == 1:
            task = cast(Any, scan_subnet).delay(
                subnet=request.subnets[0],
                scan_type=request.scan_type,
                ports=request.ports,
                dept_id=request.dept_id,
            )
        else:
            task = cast(Any, scan_subnets_batch).delay(
                subnets=request.subnets,
                scan_type=request.scan_type,
                ports=request.ports,
                dept_id=request.dept_id,
            )
        return ResponseBase(
            data=ScanTaskResponse(
                task_id=task.id,
                status="pending",
                message="扫描任务已提交",
            )
        )
    else:
        # 同步执行 (仅第一个网段)
        if not request.subnets:
            return ResponseBase(
                code=400,
                message="请提供至少一个网段",
                data=None,
            )

        result = cast(Any, scan_subnet).apply(args=[request.subnets[0], request.scan_type, request.ports])
        return ResponseBase(
            data=ScanTaskResponse(
                task_id=result.id if result else "",
                status="success",
                message="同步扫描完成",
            )
        )


@router.get(
    "/scan/task/{task_id}",
    summary="查询扫描任务状态",
    response_model=ResponseBase[ScanTaskStatus],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def get_scan_task_status(task_id: str) -> ResponseBase[ScanTaskStatus]:
    """查询 Celery 扫描任务的当前进度和最终发现的资产。

    Args:
        task_id (str): Celery 任务 ID。

    Returns:
        ResponseBase[ScanTaskStatus]: 包含状态 (PENDING/SUCCESS) 及匹配记录或错误的详情。
    """
    result = AsyncResult(task_id)

    progress = 0
    try:
        info = result.info
        if isinstance(info, dict) and isinstance(info.get("progress"), int):
            progress = int(info["progress"])
    except Exception:
        progress = 0

    status = ScanTaskStatus(
        task_id=task_id,
        status=result.status,
        progress=progress,
    )

    if result.ready():
        if result.successful():
            task_result = result.get()
            if isinstance(task_result, dict) and ("total_subnets" in task_result or "results" in task_result):
                status.result = ScanBatchResult.model_validate(task_result)
            else:
                status.result = ScanResult.model_validate(task_result)
        else:
            status.error = str(result.result)

    return ResponseBase(data=status)


# ===== 发现记录管理 =====


@router.get(
    "/",
    summary="获取发现记录列表",
    response_model=ResponseBase[PaginatedResponse[DiscoveryResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_discoveries(
    db: SessionDep,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    status: DiscoveryStatus | None = Query(None, description="状态筛选"),
    keyword: str | None = Query(None, description="关键词搜索"),
    scan_source: str | None = Query(None, description="扫描来源"),
    sort_by: str | None = Query(None, description="排序字段"),
    sort_order: str | None = Query(None, description="排序方向 (asc/desc)"),
) -> ResponseBase[PaginatedResponse[DiscoveryResponse]]:
    """获取通过网络扫描发现的所有设备记录。

    Args:
        db (Session): 数据库会话。
        page (int): 当前页码。
        page_size (int): 每页限制。
        status (DiscoveryStatus | None): 状态过滤（如：NEW, IGNORED, MATCHED）。
        keyword (str | None): 匹配 IP、MAC、主机名的搜索关键词。
        scan_source (str | None): 识别扫描的具体来源标识。

    Returns:
        ResponseBase[PaginatedResponse[DiscoveryResponse]]: 包含发现资产详情的分页响应。
    """
    items, total = await discovery_crud.get_multi_paginated(
        db,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
        scan_source=scan_source,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # 转换为响应格式
    responses = []
    for item in items:
        snmp_sysname = getattr(item, "snmp_sysname", None)
        hostname = snmp_sysname or item.hostname
        response = DiscoveryResponse(
            id=item.id,
            ip_address=item.ip_address,
            mac_address=item.mac_address,
            vendor=item.vendor,
            device_type=item.device_type,
            hostname=hostname,
            os_info=item.os_info,
            serial_number=getattr(item, "serial_number", None),
            open_ports=item.open_ports,
            ssh_banner=item.ssh_banner,
            dept_id=getattr(item, "dept_id", None),
            snmp_sysname=snmp_sysname,
            snmp_sysdescr=getattr(item, "snmp_sysdescr", None),
            snmp_ok=getattr(item, "snmp_ok", None),
            snmp_error=getattr(item, "snmp_error", None),
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

    return ResponseBase(
        data=PaginatedResponse(
            items=responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{discovery_id:uuid}",
    summary="获取发现记录详情",
    response_model=ResponseBase[DiscoveryResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def get_discovery(
    db: SessionDep,
    discovery_id: UUID,
) -> ResponseBase[DiscoveryResponse]:
    """获取单个扫描发现记录的完整属性。

    Args:
        db (Session): 数据库会话。
        discovery_id (UUID): 扫描结果主键 ID。

    Returns:
        ResponseBase[DiscoveryResponse]: 发现资产及 CMDB 匹配关联信息。
    """
    item = await discovery_crud.get(db, id=discovery_id)
    if not item:
        raise NotFoundException(message="发现记录不存在")

    response = DiscoveryResponse(
        id=item.id,
        ip_address=item.ip_address,
        mac_address=item.mac_address,
        vendor=item.vendor,
        device_type=item.device_type,
        hostname=(getattr(item, "snmp_sysname", None) or item.hostname),
        os_info=item.os_info,
        serial_number=getattr(item, "serial_number", None),
        open_ports=item.open_ports,
        ssh_banner=item.ssh_banner,
        dept_id=getattr(item, "dept_id", None),
        snmp_sysname=getattr(item, "snmp_sysname", None),
        snmp_sysdescr=getattr(item, "snmp_sysdescr", None),
        snmp_ok=getattr(item, "snmp_ok", None),
        snmp_error=getattr(item, "snmp_error", None),
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

    return ResponseBase(data=response)


@router.delete(
    "/{discovery_id:uuid}",
    summary="删除发现记录",
    response_model=ResponseBase[DeleteResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_DELETE.value]))],
)
async def delete_discovery(
    db: SessionDep,
    discovery_id: UUID,
    current_user: CurrentUser,
) -> ResponseBase[DeleteResponse]:
    """物理删除或隐藏特定的扫描发现结果。

    Args:
        db (Session): 数据库会话。
        discovery_id (UUID): 扫描记录 ID。
        current_user (CurrentUser): 当前执行操作的用户。

    Returns:
        ResponseBase[DeleteResponse]: 确认删除的消息。
    """
    success_count, _ = await discovery_crud.batch_remove(db, ids=[discovery_id])
    if success_count == 0:
        raise NotFoundException(message="发现记录不存在")

    await db.commit()
    return ResponseBase(data=DeleteResponse(message="删除成功"))


# ===== 设备纳管 =====


@router.post(
    "/{discovery_id:uuid}/adopt",
    summary="纳管设备",
    response_model=ResponseBase[AdoptResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_ADOPT.value]))],
)
async def adopt_device(
    db: SessionDep,
    discovery_id: UUID,
    request: AdoptDeviceRequest,
    scan_service: ScanServiceDep,
    current_user: CurrentUser,
) -> ResponseBase[AdoptResponse]:
    """将扫描结果中的在线资产直接录入为系统正式管理的设备。

    录入过程会预填发现的 IP、MAC、厂商等信息，并根据请求配置所属部门和凭据。

    Args:
        db (Session): 数据库会话。
        discovery_id (UUID): 发现记录关联 ID。
        request (AdoptDeviceRequest): 纳管配置，包含名称、分组、凭据等。
        scan_service (ScanService): 扫描资产服务。
        current_user (CurrentUser): 当前操作人。

    Returns:
        ResponseBase[AdoptResponse]: 包含新设备 ID 的确认响应。
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

    return ResponseBase(
        data=AdoptResponse(
            message="设备纳管成功",
            device_id=str(device.id),
            device_name=device.name,
        )
    )


# ===== 影子资产和离线设备 =====


@router.get(
    "/shadow",
    summary="获取影子资产列表",
    response_model=ResponseBase[PaginatedResponse[DiscoveryResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_shadow_assets(
    db: SessionDep,
    scan_service: ScanServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
) -> ResponseBase[PaginatedResponse[DiscoveryResponse]]:
    """获取所有已在线但尚未关联正式 CMDB 的网路资产。

    Args:
        db (Session): 数据库会话。
        scan_service (ScanService): 扫描资产服务依赖。
        page (int): 当前页码。
        page_size (int): 每页限制。

    Returns:
        ResponseBase[PaginatedResponse[DiscoveryResponse]]: 影子资产（未知资产）列表。
    """
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
            serial_number=getattr(item, "serial_number", None),
            open_ports=item.open_ports,
            ssh_banner=item.ssh_banner,
            dept_id=getattr(item, "dept_id", None),
            snmp_sysname=getattr(item, "snmp_sysname", None),
            snmp_sysdescr=getattr(item, "snmp_sysdescr", None),
            snmp_ok=getattr(item, "snmp_ok", None),
            snmp_error=getattr(item, "snmp_error", None),
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

    return ResponseBase(
        data=PaginatedResponse(
            items=responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/offline",
    summary="获取离线设备列表",
    response_model=ResponseBase[list[OfflineDevice]],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_LIST.value]))],
)
async def list_offline_devices(
    db: SessionDep,
    scan_service: ScanServiceDep,
    days_threshold: int = Query(7, ge=1, description="离线天数阈值"),
) -> ResponseBase[list[OfflineDevice]]:
    """获取由于长时间未能在扫描中发现而标记为离线的设备列表。

    系统会将 CMDB 中的设备与最新的扫描记录比对，若超过阈值天数未出现，则视为离线。

    Args:
        db (Session): 数据库会话。
        scan_service (ScanService): 扫描资产服务。
        days_threshold (int): 判定离线的天数阈值（默认为 7 天）。

    Returns:
        ResponseBase[list[OfflineDevice]]: 包含设备 ID、名称及其最后一次被扫描到的时间。
    """
    devices = await scan_service.detect_offline_devices(db, days_threshold=days_threshold)
    return ResponseBase(data=devices)


# ===== CMDB 比对 =====


@router.post(
    "/compare",
    summary="执行 CMDB 比对",
    response_model=ResponseBase[ScanTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DISCOVERY_SCAN.value]))],
)
async def trigger_cmdb_compare(
    current_user: CurrentUser,
    async_mode: bool = Query(True, description="是否异步执行"),
) -> ResponseBase[ScanTaskResponse]:
    """全量对比当前的扫描发现库与正式 CMDB 设备库。

    用于同步状态、识别影子资产和更新离线天数统计。建议在完成全网大规模扫描后执行。

    Args:
        current_user (CurrentUser): 当前操作人。
        async_mode (bool): 是否进入 Celery 异步处理模式。

    Returns:
        ResponseBase[ScanTaskResponse]: 包含任务状态的响应。
    """
    if async_mode:
        task = cast(Any, compare_cmdb).delay()
        return ResponseBase(
            data=ScanTaskResponse(
                task_id=task.id,
                status="pending",
                message="CMDB 比对任务已提交",
            )
        )
    else:
        result = cast(Any, compare_cmdb).apply()
        return ResponseBase(
            data=ScanTaskResponse(
                task_id=result.id if result else "",
                status="success",
                message="CMDB 比对完成",
            )
        )
