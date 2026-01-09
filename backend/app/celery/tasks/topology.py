"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology.py
@DateTime: 2026-01-09 23:55:00
@Docs: 网络拓扑 Celery 任务 (Topology Tasks).

包含 LLDP 拓扑采集、拓扑刷新等异步任务�?
"""

from typing import Any
from uuid import UUID

from app.celery.app import celery_app
from app.celery.base import BaseTask
from app.core.cache import redis_client
from app.core.db import AsyncSessionLocal
from app.core.logger import logger
from app.crud.crud_device import device as device_crud
from app.crud.crud_topology import topology_crud
from app.services.topology_service import TopologyService


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.collect_topology",
    queue="topology",
)
def collect_topology(
    self,
    device_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    采集网络拓扑 (LLDP) �?Celery 任务�?

    Args:
        device_ids: 指定设备ID列表 (为空则采集所�?

    Returns:
        采集结果
    """
    import asyncio

    async def _collect():
        async with AsyncSessionLocal() as db:
            topology_service = TopologyService(
                topology_crud=topology_crud,
                device_crud=device_crud,
                redis_client=redis_client,
            )

            # 转换设备ID
            uuids = [UUID(did) for did in device_ids] if device_ids else None

            # 执行采集
            result = await topology_service.collect_lldp_all(db, device_ids=uuids)
            result.task_id = self.request.id

            logger.info(
                "拓扑采集完成",
                total_devices=result.total_devices,
                success=result.success_count,
                failed=result.failed_count,
                total_links=result.total_links,
            )

            return result.model_dump()

    return asyncio.run(_collect())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.collect_device_topology",
    queue="topology",
)
def collect_device_topology(self, device_id: str) -> dict[str, Any]:
    """
    采集单个设备拓扑�?Celery 任务�?

    Args:
        device_id: 设备ID

    Returns:
        采集结果
    """
    import asyncio

    async def _collect_single():
        async with AsyncSessionLocal() as db:
            topology_service = TopologyService(
                topology_crud=topology_crud,
                device_crud=device_crud,
                redis_client=redis_client,
            )

            result = await topology_service.collect_lldp_all(db, device_ids=[UUID(device_id)])
            result.task_id = self.request.id

            # 返回单设备结�?
            device_result = result.results[0] if result.results else None

            return {
                "task_id": self.request.id,
                "device_id": device_id,
                "success": device_result.success if device_result else False,
                "neighbors_count": device_result.neighbors_count if device_result else 0,
                "neighbors": device_result.neighbors if device_result else [],
                "error": device_result.error if device_result else "Device not found",
            }

    return asyncio.run(_collect_single())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.scheduled_topology_refresh",
    queue="topology",
)
def scheduled_topology_refresh(self) -> dict[str, Any]:
    """
    定时拓扑刷新任务 (�?Celery Beat 调度)�?

    采集所有活跃设备的 LLDP 信息并更新拓扑数据�?

    Returns:
        刷新结果
    """
    import asyncio

    async def _refresh():
        async with AsyncSessionLocal() as db:
            topology_service = TopologyService(
                topology_crud=topology_crud,
                device_crud=device_crud,
                redis_client=redis_client,
            )

            # 采集所有设�?
            result = await topology_service.collect_lldp_all(db)
            result.task_id = self.request.id

            logger.info(
                "定时拓扑刷新完成",
                total_devices=result.total_devices,
                success=result.success_count,
                failed=result.failed_count,
                total_links=result.total_links,
            )

            return result.model_dump()

    return asyncio.run(_refresh())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.build_topology_cache",
    queue="topology",
)
def build_topology_cache(self) -> dict[str, Any]:
    """
    构建拓扑缓存�?Celery 任务�?

    从数据库构建 vis.js 格式的拓扑数据并缓存�?Redis�?

    Returns:
        构建结果
    """
    import asyncio

    async def _build_cache():
        async with AsyncSessionLocal() as db:
            topology_service = TopologyService(
                topology_crud=topology_crud,
                device_crud=device_crud,
                redis_client=redis_client,
            )

            topology = await topology_service.build_topology(db)

            logger.info(
                "拓扑缓存构建完成",
                nodes=topology.stats.total_nodes,
                edges=topology.stats.total_edges,
            )

            return {
                "task_id": self.request.id,
                "nodes_count": topology.stats.total_nodes,
                "edges_count": topology.stats.total_edges,
                "cmdb_devices": topology.stats.cmdb_devices,
                "unknown_devices": topology.stats.unknown_devices,
            }

    return asyncio.run(_build_cache())
