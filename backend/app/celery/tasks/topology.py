"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology.py
@DateTime: 2026-01-09 23:55:00
@Docs: 网络拓扑 Celery 任务 (Topology Tasks).

包含 LLDP 拓扑采集、拓扑刷新等异步任务。
"""

from typing import Any
from uuid import UUID

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async, safe_update_state
from app.core import cache as cache_module
from app.core.db import AsyncSessionLocal
from app.core.exceptions import OTPRequiredException
from app.core.logger import celery_details_logger, celery_task_logger
from app.crud.crud_credential import credential as credential_crud
from app.crud.crud_device import device as device_crud
from app.crud.crud_topology import topology_crud
from app.services.topology_service import TopologyService


def _create_topology_service() -> TopologyService:
    """创建 TopologyService 实例的工厂函数。"""
    return TopologyService(
        topology_crud=topology_crud,
        device_crud=device_crud,
        credential_crud=credential_crud,
        redis_client=cache_module.redis_client,
    )


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
    采集网络拓扑 (LLDP) - Celery 任务。

    Args:
        device_ids: 指定设备ID列表 (为空则采集所有设备)

    Returns:
        采集结果，如果需要 OTP 则返回 otp_required 状态
    """
    # 在同步上下文中获取 Celery 任务 ID（在进入异步之前）
    celery_task_id = self.request.id

    # 进度回调函数（使用闭包捕获 celery_task_id）
    def update_progress(progress: int, message: str):
        safe_update_state(
            self,
            celery_task_id,
            state="PROGRESS",
            meta={"progress": progress, "message": message},
        )

    async def _collect():
        async with AsyncSessionLocal() as db:
            topology_service = _create_topology_service()

            # 转换设备ID
            uuids = [UUID(did) for did in device_ids] if device_ids else None

            try:
                # 执行采集
                result = await topology_service.collect_lldp_all(
                    db, device_ids=uuids, progress_callback=update_progress
                )
                result.task_id = celery_task_id

                celery_task_logger.info(
                    "拓扑采集完成",
                    total_devices=result.total_devices,
                    success=result.success_count,
                    failed=result.failed_count,
                    total_links=result.total_links,
                )

                # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
                return result.model_dump(mode="json")

            except OTPRequiredException as e:
                # 返回 OTP 所需信息，不抛出异常
                celery_task_logger.info(
                    "拓扑采集需要 OTP",
                    dept_id=e.dept_id_str,
                    device_group=e.device_group,
                    failed_devices=e.failed_devices,
                )
                return {
                    "task_id": self.request.id,
                    "status": "otp_required",
                    "otp_required": True,
                    "dept_id": e.dept_id_str,
                    "device_group": e.device_group,
                    "failed_devices": e.failed_devices,
                    "message": e.message,
                }

    return run_async(_collect())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.collect_device_topology",
    queue="topology",
)
def collect_device_topology(self, device_id: str) -> dict[str, Any]:
    """
    采集单个设备拓扑 - Celery 任务。

    Args:
        device_id: 设备ID

    Returns:
        采集结果，如果需要 OTP 则返回 otp_required 状态
    """

    async def _collect_single():
        async with AsyncSessionLocal() as db:
            topology_service = _create_topology_service()

            try:
                result = await topology_service.collect_lldp_all(db, device_ids=[UUID(device_id)])
                result.task_id = self.request.id

                # 返回单设备结果
                device_result = result.results[0] if result.results else None

                return {
                    "task_id": self.request.id,
                    "device_id": device_id,
                    "success": device_result.success if device_result else False,
                    "neighbors_count": device_result.neighbors_count if device_result else 0,
                    "neighbors": device_result.neighbors if device_result else [],
                    "error": device_result.error if device_result else "Device not found",
                }

            except OTPRequiredException as e:
                celery_task_logger.info(
                    "单设备拓扑采集需要 OTP",
                    device_id=device_id,
                    dept_id=e.dept_id_str,
                    device_group=e.device_group,
                )
                return {
                    "task_id": self.request.id,
                    "device_id": device_id,
                    "status": "otp_required",
                    "otp_required": True,
                    "dept_id": e.dept_id_str,
                    "device_group": e.device_group,
                    "failed_devices": e.failed_devices,
                    "message": e.message,
                }

    return run_async(_collect_single())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.scheduled_topology_refresh",
    queue="topology",
)
def scheduled_topology_refresh(self) -> dict[str, Any]:
    """
    定时拓扑刷新任务 (通过 Celery Beat 调度)

    采集所有活跃设备的 LLDP 信息并更新拓扑数据。

    注意：OTP 手动认证的设备在定时任务中会被跳过（定时任务无法等待用户输入）。

    Returns:
        刷新结果
    """
    # 在同步上下文中获取 Celery 任务 ID（在进入异步之前）
    celery_task_id = self.request.id

    # 进度回调函数（使用闭包捕获 celery_task_id）
    def update_progress(progress: int, message: str):
        safe_update_state(
            self,
            celery_task_id,
            state="PROGRESS",
            meta={"progress": progress, "message": message},
        )

    async def _refresh():
        async with AsyncSessionLocal() as db:
            topology_service = _create_topology_service()

            try:
                # 采集所有设备
                result = await topology_service.collect_lldp_all(
                    db, skip_otp_manual=True, progress_callback=update_progress
                )
                result.task_id = celery_task_id

                celery_task_logger.info(
                    "定时拓扑刷新完成",
                    total_devices=result.total_devices,
                    success=result.success_count,
                    failed=result.failed_count,
                    total_links=result.total_links,
                )

                # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
                return result.model_dump(mode="json")

            except OTPRequiredException as e:
                # 定时任务不应该触发 OTP，记录警告并跳过
                celery_task_logger.warning(
                    "定时拓扑刷新遇到 OTP 需求（已跳过）",
                    dept_id=e.dept_id_str,
                    device_group=e.device_group,
                )
                return {
                    "task_id": self.request.id,
                    "status": "partial",
                    "message": "部分设备因需要 OTP 而跳过",
                    "skipped_otp_groups": [
                        {"dept_id": e.dept_id_str, "device_group": e.device_group}
                    ],
                }

    return run_async(_refresh())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.topology.build_topology_cache",
    queue="topology",
)
def build_topology_cache(self) -> dict[str, Any]:
    """
    构建拓扑缓存 - Celery 任务。

    从数据库构建 vis.js 格式的拓扑数据并缓存到 Redis。

    Returns:
        构建结果
    """

    async def _build_cache():
        async with AsyncSessionLocal() as db:
            topology_service = _create_topology_service()

            topology = await topology_service.build_topology(db)

            celery_task_logger.info(
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

    return run_async(_build_cache())
