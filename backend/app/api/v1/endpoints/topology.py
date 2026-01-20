"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology.py
@DateTime: 2026-01-10 00:20:00
@Docs: 网络拓扑 API 端点 (Topology Endpoints).

提供 LLDP 拓扑采集、拓扑数据查询、vis.js 格式输出等功能。
"""

from typing import Any, cast
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import (
    CurrentUser,
    SessionDep,
    TopologyServiceDep,
    require_permissions,
)
from app.celery.tasks.topology import (
    build_topology_cache,
    collect_device_topology,
    collect_topology,
)
from app.core.permissions import PermissionCode
from app.schemas.common import ResponseBase
from app.schemas.topology import (
    DeviceNeighborsResponse,
    TopologyCollectRequest,
    TopologyCollectResult,
    TopologyLinksResponse,
    TopologyResponse,
    TopologyTaskResponse,
    TopologyTaskStatus,
)

router = APIRouter(tags=["网络拓扑"])


# ===== 拓扑数据查询 =====


@router.get(
    "/",
    summary="获取拓扑数据",
    response_model=ResponseBase[TopologyResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_topology(
    db: SessionDep,
    topology_service: TopologyServiceDep,
) -> ResponseBase[TopologyResponse]:
    """获取完整的网络拓扑数据，用于前端 vis.js 或相关拓扑引擎渲染。

    Args:
        db (Session): 数据库会话。
        topology_service (TopologyService): 拓扑服务依赖。

    Returns:
        ResponseBase[TopologyResponse]: 包含节点 (nodes)、边 (edges) 和统计数据的对象。
    """
    data = await topology_service.build_topology(db)
    return ResponseBase(data=data)


@router.get(
    "/links",
    summary="获取链路列表",
    response_model=ResponseBase[TopologyLinksResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def list_topology_links(
    db: SessionDep,
    topology_service: TopologyServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ResponseBase[TopologyLinksResponse]:
    """分页获取所有已发现的网络链路列表。

    Args:
        db (Session): 数据库会话。
        topology_service (TopologyService): 拓扑服务依赖。
        page (int): 页码。
        page_size (int): 每页条数。

    Returns:
        ResponseBase[TopologyLinksResponse]: 包含 links 列表和分页信息的响应。
    """
    links, total = await topology_service.get_all_links(db, page=page, page_size=page_size)

    items = [
        {
            "id": str(link.id),
            "source_device_id": str(link.source_device_id),
            "source_interface": link.source_interface,
            "target_device_id": str(link.target_device_id) if link.target_device_id else None,
            "target_interface": link.target_interface,
            "target_hostname": link.target_hostname,
            "target_ip": link.target_ip,
            "link_type": link.link_type,
            "collected_at": link.collected_at.isoformat() if link.collected_at else None,
        }
        for link in links
    ]

    return ResponseBase(
        data=TopologyLinksResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/device/{device_id}/neighbors",
    summary="获取设备邻居",
    response_model=ResponseBase[DeviceNeighborsResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_device_neighbors(
    db: SessionDep,
    device_id: UUID,
    topology_service: TopologyServiceDep,
) -> ResponseBase[DeviceNeighborsResponse]:
    """获取指定设备的所有直接连接的邻居链路。

    Args:
        db (Session): 数据库会话。
        device_id (UUID): 设备 ID。
        topology_service (TopologyService): 拓扑服务依赖。

    Returns:
        ResponseBase[DeviceNeighborsResponse]: 邻居链路列表。
    """
    data = await topology_service.get_device_neighbors(db, device_id=device_id)
    return ResponseBase(data=data)


@router.get(
    "/export",
    summary="导出拓扑数据",
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def export_topology(
    db: SessionDep,
    topology_service: TopologyServiceDep,
) -> JSONResponse:
    """导出全量拓扑数据为 JSON 文件。

    Args:
        db (Session): 数据库会话。
        topology_service (TopologyService): 拓扑服务依赖。

    Returns:
        JSONResponse: 下载响应。
    """
    data = await topology_service.export_topology(db)

    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": "attachment; filename=topology_export.json",
        },
    )


# ===== 拓扑采集 =====


@router.post(
    "/refresh",
    summary="刷新拓扑",
    response_model=ResponseBase[TopologyTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def refresh_topology(
    request: TopologyCollectRequest,
    current_user: CurrentUser,
) -> ResponseBase[TopologyTaskResponse]:
    """触发全局或指定范围的拓扑发现任务。

    Args:
        request (TopologyCollectRequest): 采集请求参数，包括指定设备列表和是否异步。
        current_user (User): 当前操作用户。

    Returns:
        ResponseBase[TopologyTaskResponse]: 任务 ID 或同步执行结果。
    """
    device_ids = [str(d) for d in request.device_ids] if request.device_ids else None

    if request.async_mode:
        task = cast(Any, collect_topology).delay(device_ids=device_ids)
        return ResponseBase(
            data=TopologyTaskResponse(
                task_id=task.id,
                status="pending",
                message="拓扑采集任务已提交",
            )
        )
    else:
        # 同步执行
        result = cast(Any, collect_topology).apply(kwargs={"device_ids": device_ids})
        return ResponseBase(
            data=TopologyTaskResponse(
                task_id=result.id if result else "",
                status="success",
                message="同步拓扑采集完成",
            )
        )


@router.post(
    "/device/{device_id}/collect",
    summary="采集单设备拓扑",
    response_model=ResponseBase[TopologyTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def collect_single_device_topology(
    device_id: UUID,
    current_user: CurrentUser,
    async_mode: bool = Query(True),
) -> ResponseBase[TopologyTaskResponse]:
    """针对单个特定设备执行 LLDP 邻居采集。

    Args:
        device_id (UUID): 设备 ID。
        current_user (User): 当前用户。
        async_mode (bool): 是否异步模式。

    Returns:
        ResponseBase[TopologyTaskResponse]: 任务 ID 或执行信息。
    """
    if async_mode:
        task = cast(Any, collect_device_topology).delay(device_id=str(device_id))
        return ResponseBase(
            data=TopologyTaskResponse(
                task_id=task.id,
                status="pending",
                message="设备拓扑采集任务已提交",
            )
        )
    else:
        result = cast(Any, collect_device_topology).apply(args=[str(device_id)])
        return ResponseBase(
            data=TopologyTaskResponse(
                task_id=result.id if result else "",
                status="success",
                message="同步设备拓扑采集完成",
            )
        )


@router.get(
    "/task/{task_id}",
    summary="查询拓扑任务状态",
    response_model=ResponseBase[TopologyTaskStatus],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_topology_task_status(task_id: str) -> ResponseBase[TopologyTaskStatus] | JSONResponse:
    """查询拓扑采集后台任务的执行实时状态。

    Args:
        task_id (str): Celery 任务 ID。

    Returns:
        ResponseBase[TopologyTaskStatus]: 任务状态和（如有）结果数据。
    """
    result = AsyncResult(task_id)

    status = TopologyTaskStatus(
        task_id=task_id,
        status=result.status,
    )

    if result.ready():
        if result.successful():
            task_result = result.get()
            status.result = TopologyCollectResult.model_validate(task_result)
        else:
            status.error = str(result.result)
            from app.core.otp_notice import build_otp_required_response, is_otp_error_text

            if is_otp_error_text(status.error):
                return build_otp_required_response(
                    message=status.error,
                    details={"otp_required": True},
                )

    return ResponseBase(data=status)


@router.post(
    "/cache/rebuild",
    summary="重建拓扑缓存",
    response_model=ResponseBase[TopologyTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def rebuild_topology_cache(
    current_user: CurrentUser,
) -> ResponseBase[TopologyTaskResponse]:
    """强制重新从数据库构建拓扑缓存并更新到 Redis。

    Args:
        current_user (User): 当前用户。

    Returns:
        ResponseBase[TopologyTaskResponse]: 任务 ID 信息。
    """
    task = cast(Any, build_topology_cache).delay()
    return ResponseBase(
        data=TopologyTaskResponse(
            task_id=task.id,
            status="pending",
            message="拓扑缓存重建任务已提交",
        )
    )
