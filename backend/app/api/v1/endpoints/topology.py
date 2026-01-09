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
from app.schemas.topology import (
    DeviceNeighborsResponse,
    TopologyCollectRequest,
    TopologyCollectResult,
    TopologyResponse,
    TopologyTaskStatus,
)

router = APIRouter(prefix="/topology", tags=["网络拓扑"])


# ===== 拓扑数据查询 =====


@router.get(
    "/",
    summary="获取拓扑数据",
    response_model=TopologyResponse,
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_topology(
    db: SessionDep,
    topology_service: TopologyServiceDep,
) -> TopologyResponse:
    """
    获取完整的网络拓扑数据 (vis.js 格式)。

    返回格式：
    - nodes: 节点列表 (设备)
    - edges: 边列表 (链路)
    - stats: 统计信息
    """
    return await topology_service.build_topology(db)


@router.get(
    "/links",
    summary="获取链路列表",
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def list_topology_links(
    db: SessionDep,
    topology_service: TopologyServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取所有拓扑链路 (分页)。"""
    links, total = await topology_service.get_all_links(db, page=page, page_size=page_size)

    return {
        "items": [
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
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/device/{device_id}/neighbors",
    summary="获取设备邻居",
    response_model=DeviceNeighborsResponse,
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_device_neighbors(
    db: SessionDep,
    device_id: UUID,
    topology_service: TopologyServiceDep,
) -> DeviceNeighborsResponse:
    """获取指定设备的所有邻居链路。"""
    return await topology_service.get_device_neighbors(db, device_id=device_id)


@router.get(
    "/export",
    summary="导出拓扑数据",
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def export_topology(
    db: SessionDep,
    topology_service: TopologyServiceDep,
) -> JSONResponse:
    """导出拓扑数据为 JSON 格式 (可用于离线查看或备份)。"""
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
    response_model=dict[str, Any],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def refresh_topology(
    request: TopologyCollectRequest,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """
    触发拓扑刷新任务 (采集 LLDP 信息)。

    - 可指定设备列表，为空则采集所有活跃设备
    - async_mode=True 时返回任务ID
    """
    device_ids = [str(d) for d in request.device_ids] if request.device_ids else None

    if request.async_mode:
        task = cast(Any, collect_topology).delay(device_ids=device_ids)
        return {
            "task_id": task.id,
            "status": "pending",
            "message": "拓扑采集任务已提交",
        }
    else:
        # 同步执行
        result = cast(Any, collect_topology).apply(kwargs={"device_ids": device_ids})
        return result.get()


@router.post(
    "/device/{device_id}/collect",
    summary="采集单设备拓扑",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def collect_single_device_topology(
    device_id: UUID,
    current_user: CurrentUser,
    async_mode: bool = Query(True),
) -> dict[str, Any]:
    """采集单个设备的 LLDP 邻居信息。"""
    if async_mode:
        task = cast(Any, collect_device_topology).delay(device_id=str(device_id))
        return {
            "task_id": task.id,
            "status": "pending",
            "message": "设备拓扑采集任务已提交",
        }
    else:
        result = cast(Any, collect_device_topology).apply(args=[str(device_id)])
        return result.get()


@router.get(
    "/task/{task_id}",
    summary="查询拓扑任务状态",
    response_model=TopologyTaskStatus,
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_VIEW.value]))],
)
async def get_topology_task_status(task_id: str) -> TopologyTaskStatus:
    """查询拓扑采集任务的执行状态和结果。"""
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

    return status


@router.post(
    "/cache/rebuild",
    summary="重建拓扑缓存",
    dependencies=[Depends(require_permissions([PermissionCode.TOPOLOGY_REFRESH.value]))],
)
async def rebuild_topology_cache(
    current_user: CurrentUser,
) -> dict[str, Any]:
    """手动重建拓扑缓存 (从数据库读取并缓存到 Redis)。"""
    task = cast(Any, build_topology_cache).delay()
    return {
        "task_id": task.id,
        "status": "pending",
        "message": "拓扑缓存重建任务已提交",
    }
