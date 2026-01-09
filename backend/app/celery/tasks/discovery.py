"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-09 23:50:00
@Docs: 设备发现 Celery 任务 (Discovery Tasks).

包含网络扫描、CMDB 比对等异步任务。
"""

from typing import Any

from app.celery.app import celery_app
from app.celery.base import BaseTask
from app.core.db import AsyncSessionLocal
from app.core.logger import logger
from app.crud.crud_device import device as device_crud
from app.crud.crud_discovery import discovery_crud
from app.services.scan_service import ScanService


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scan_subnet",
    queue="discovery",
)
def scan_subnet(
    self,
    subnet: str,
    scan_type: str = "nmap",
    ports: str | None = None,
) -> dict[str, Any]:
    """
    扫描单个网段的 Celery 任务。

    Args:
        subnet: 网段 (CIDR 格式)
        scan_type: 扫描类型 (nmap/masscan)
        ports: 扫描端口

    Returns:
        扫描结果字典
    """
    import asyncio

    async def _scan():
        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            # 执行扫描
            if scan_type == "masscan":
                result = await scan_service.masscan_scan(subnet, ports=ports)
            else:
                result = await scan_service.nmap_scan(subnet, ports=ports)

            # 处理扫描结果
            if result.hosts:
                result.task_id = self.request.id
                processed = await scan_service.process_scan_result(
                    db, scan_result=result, scan_task_id=self.request.id
                )
                logger.info(
                    "扫描结果处理完成",
                    subnet=subnet,
                    hosts_found=result.hosts_found,
                    processed=processed,
                )

            return result.model_dump()

    return asyncio.get_event_loop().run_until_complete(_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scan_subnets_batch",
    queue="discovery",
)
def scan_subnets_batch(
    self,
    subnets: list[str],
    scan_type: str = "nmap",
    ports: str | None = None,
) -> dict[str, Any]:
    """
    批量扫描多个网段。

    Args:
        subnets: 网段列表
        scan_type: 扫描类型
        ports: 扫描端口

    Returns:
        批量扫描结果
    """
    import asyncio

    async def _batch_scan():
        results = []
        total_hosts = 0

        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            for subnet in subnets:
                try:
                    # 执行扫描
                    if scan_type == "masscan":
                        result = await scan_service.masscan_scan(subnet, ports=ports)
                    else:
                        result = await scan_service.nmap_scan(subnet, ports=ports)

                    # 处理结果
                    if result.hosts:
                        result.task_id = self.request.id
                        await scan_service.process_scan_result(
                            db, scan_result=result, scan_task_id=self.request.id
                        )
                        total_hosts += result.hosts_found

                    results.append({
                        "subnet": subnet,
                        "hosts_found": result.hosts_found,
                        "error": result.error,
                    })

                except Exception as e:
                    logger.error(f"扫描网段失败: {subnet}", error=str(e))
                    results.append({
                        "subnet": subnet,
                        "hosts_found": 0,
                        "error": str(e),
                    })

        return {
            "task_id": self.request.id,
            "total_subnets": len(subnets),
            "total_hosts": total_hosts,
            "results": results,
        }

    return asyncio.get_event_loop().run_until_complete(_batch_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.compare_cmdb",
    queue="discovery",
)
def compare_cmdb(self) -> dict[str, Any]:
    """
    将扫描发现与 CMDB 比对的 Celery 任务。

    Returns:
        比对结果
    """
    import asyncio

    async def _compare():
        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            result = await scan_service.compare_with_cmdb(db)

            logger.info(
                "CMDB 比对完成",
                total_discovered=result.total_discovered,
                matched=result.matched,
                shadow_assets=result.shadow_assets,
                offline_devices=result.offline_devices,
            )

            return result.model_dump()

    return asyncio.get_event_loop().run_until_complete(_compare())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scheduled_network_scan",
    queue="discovery",
)
def scheduled_network_scan(self) -> dict[str, Any]:
    """
    定时网络扫描任务 (由 Celery Beat 调度)。

    扫描预配置的网段列表，并与 CMDB 比对。

    Returns:
        扫描和比对结果
    """
    import asyncio

    async def _scheduled_scan():
        # TODO: 从配置或数据库获取待扫描网段列表
        # 这里先返回空结果，实际使用时应配置网段
        subnets: list[str] = []

        if not subnets:
            logger.warning("定时扫描：未配置待扫描网段")
            return {
                "task_id": self.request.id,
                "message": "未配置待扫描网段",
                "scanned": False,
            }

        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            total_hosts = 0
            scan_results = []

            for subnet in subnets:
                try:
                    result = await scan_service.nmap_scan(subnet)
                    if result.hosts:
                        result.task_id = self.request.id
                        await scan_service.process_scan_result(
                            db, scan_result=result, scan_task_id=self.request.id
                        )
                        total_hosts += result.hosts_found
                    scan_results.append({
                        "subnet": subnet,
                        "hosts_found": result.hosts_found,
                    })
                except Exception as e:
                    logger.error(f"定时扫描失败: {subnet}", error=str(e))
                    scan_results.append({
                        "subnet": subnet,
                        "error": str(e),
                    })

            # 比对 CMDB
            compare_result = await scan_service.compare_with_cmdb(db)

            return {
                "task_id": self.request.id,
                "total_subnets": len(subnets),
                "total_hosts": total_hosts,
                "scan_results": scan_results,
                "compare_result": compare_result.model_dump(),
            }

    return asyncio.get_event_loop().run_until_complete(_scheduled_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.increment_offline_days",
    queue="discovery",
)
def increment_offline_days(self) -> dict[str, Any]:
    """
    增加发现记录的离线天数 (每日执行一次)。

    Returns:
        更新结果
    """
    import asyncio

    async def _increment():
        async with AsyncSessionLocal() as db:
            count = await discovery_crud.increment_offline_days(db)
            await db.commit()

            logger.info("离线天数更新完成", updated_count=count)

            return {
                "task_id": self.request.id,
                "updated_count": count,
            }

    return asyncio.get_event_loop().run_until_complete(_increment())
