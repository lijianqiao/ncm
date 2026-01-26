"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-09 23:50:00
@Docs: 设备发现 Celery 任务 (Discovery Tasks).

包含网络扫描、CMDB 比对等异步任务
"""

from typing import Any
from uuid import UUID

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async, safe_update_state
from app.core.db import AsyncSessionLocal
from app.core.logger import logger
from app.crud.crud_device import device as device_crud
from app.crud.crud_discovery import discovery_crud
from app.schemas.discovery import ScanResult as ScanResultSchema
from app.services.scan_service import ScanService


def _parse_snmp_cred_uuid(snmp_cred_id: str | None) -> "UUID | None":
    if not snmp_cred_id:
        return None
    try:
        return UUID(str(snmp_cred_id))
    except (ValueError, TypeError):
        return None


async def _execute_scan(
    scan_service: ScanService,
    subnet: str,
    scan_type: str = "auto",
    ports: str | None = None,
) -> ScanResultSchema:
    """执行单个网段扫描的共用逻辑。

    Args:
        scan_service: 扫描服务实例
        subnet: 网段 (CIDR 格式)
        scan_type: 扫描类型 (nmap/masscan/auto)
        ports: 扫描端口

    Returns:
        扫描结果 Schema
    """
    from datetime import datetime

    resolved = scan_service.resolve_scan_type(scan_type)

    if resolved == "masscan":
        return await scan_service.masscan_scan(subnet, ports=ports)
    if resolved == "nmap":
        return await scan_service.nmap_scan(subnet, ports=ports)

    # 未检测到可用扫描器
    return ScanResultSchema(
        subnet=subnet,
        scan_type="auto",
        hosts_found=0,
        hosts=[],
        started_at=datetime.now(),
        completed_at=datetime.now(),
        duration_seconds=0,
        error="未检测到可用扫描器：请安装 nmap 或 masscan，并确保在 PATH 中",
    )


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scan_subnet",
    queue="discovery",
)
def scan_subnet(
    self,
    subnet: str,
    scan_type: str = "auto",
    ports: str | None = None,
    snmp_cred_id: str | None = None,
) -> dict[str, Any]:
    """
    扫描单个网段 Celery 任务。

    Args:
        subnet: 网段 (CIDR 格式)
        scan_type: 扫描类型 (nmap/masscan)
        ports: 扫描端口

    Returns:
        扫描结果字典
    """

    celery_task_id = self.request.id
    snmp_cred_uuid = _parse_snmp_cred_uuid(snmp_cred_id)

    async def _scan():
        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            # 阶段：开始扫描
            safe_update_state(
                self,
                celery_task_id,
                state="PROGRESS",
                meta={"progress": 5, "stage": "scanning", "subnet": subnet},
            )

            # 执行扫描（使用共用函数）
            result = await _execute_scan(scan_service, subnet, scan_type, ports)

            # 阶段：扫描完成，准备入库
            safe_update_state(
                self,
                celery_task_id,
                state="PROGRESS",
                meta={"progress": 70, "stage": "saving", "subnet": subnet, "hosts_found": result.hosts_found},
            )

            # 处理扫描结果
            result.task_id = celery_task_id
            if result.hosts:
                safe_update_state(
                    self,
                    celery_task_id,
                    state="PROGRESS",
                    meta={"progress": 80, "stage": "enriching", "subnet": subnet, "hosts_found": result.hosts_found},
                )
                processed = await scan_service.process_scan_result(
                    db,
                    scan_result=result,
                    scan_task_id=celery_task_id,
                    snmp_cred_id=snmp_cred_uuid,
                )
                logger.info(
                    "扫描结果处理完成",
                    subnet=subnet,
                    hosts_found=result.hosts_found,
                    processed=processed,
                )

            # 阶段：完成
            safe_update_state(
                self,
                celery_task_id,
                state="PROGRESS",
                meta={"progress": 100, "stage": "done", "subnet": subnet},
            )

            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            return result.model_dump(mode="json")

    return run_async(_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scan_subnets_batch",
    queue="discovery",
)
def scan_subnets_batch(
    self,
    subnets: list[str],
    scan_type: str = "auto",
    ports: str | None = None,
    snmp_cred_id: str | None = None,
) -> dict[str, Any]:
    """
    批量扫描多个网段 Celery 任务。

    Args:
        subnets: 网段列表
        scan_type: 扫描类型
        ports: 扫描端口

    Returns:
        批量扫描结果
    """

    celery_task_id = self.request.id
    snmp_cred_uuid = _parse_snmp_cred_uuid(snmp_cred_id)

    async def _batch_scan():
        results = []
        total_hosts = 0

        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            total = len(subnets) if subnets else 0

            for idx, subnet in enumerate(subnets, start=1):
                try:
                    base_progress = int(((idx - 1) / max(total, 1)) * 100)
                    safe_update_state(
                        self,
                        celery_task_id,
                        state="PROGRESS",
                        meta={
                            "progress": base_progress,
                            "stage": "scanning",
                            "subnet": subnet,
                            "current": idx,
                            "total": total,
                        },
                    )

                    # 执行扫描（使用共用函数）
                    result = await _execute_scan(scan_service, subnet, scan_type, ports)

                    safe_update_state(
                        self,
                        celery_task_id,
                        state="PROGRESS",
                        meta={
                            "progress": min(base_progress + 10, 95),
                            "stage": "saving",
                            "subnet": subnet,
                            "current": idx,
                            "total": total,
                            "hosts_found": result.hosts_found,
                        },
                    )

                    # 处理结果
                    if result.hosts:
                        result.task_id = celery_task_id
                        safe_update_state(
                            self,
                            celery_task_id,
                            state="PROGRESS",
                            meta={
                                "progress": min(base_progress + 15, 95),
                                "stage": "enriching",
                                "subnet": subnet,
                                "current": idx,
                                "total": total,
                                "hosts_found": result.hosts_found,
                            },
                        )
                        await scan_service.process_scan_result(
                            db,
                            scan_result=result,
                            scan_task_id=celery_task_id,
                            snmp_cred_id=snmp_cred_uuid,
                        )
                        total_hosts += result.hosts_found

                    results.append(
                        {
                            "subnet": subnet,
                            "hosts_found": result.hosts_found,
                            "error": result.error,
                        }
                    )

                except Exception as e:
                    logger.error(f"扫描网段失败: {subnet}", error=str(e))
                    results.append(
                        {
                            "subnet": subnet,
                            "hosts_found": 0,
                            "error": str(e),
                        }
                    )

            safe_update_state(
                self,
                celery_task_id,
                state="PROGRESS",
                meta={"progress": 100, "stage": "done", "total_hosts": total_hosts},
            )

        return {
            "task_id": celery_task_id,
            "total_subnets": len(subnets),
            "total_hosts": total_hosts,
            "results": results,
        }

    return run_async(_batch_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.compare_cmdb",
    queue="discovery",
)
def compare_cmdb(self) -> dict[str, Any]:
    """
    将扫描发现与 CMDB 比对 Celery 任务。

    Returns:
        比对结果
    """

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

            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            return result.model_dump(mode="json")

    return run_async(_compare())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.scheduled_network_scan",
    queue="discovery",
)
def scheduled_network_scan(self) -> dict[str, Any]:
    """
    定时网络扫描任务 (通过 Celery Beat 调度)

    扫描预配置的网段列表，并与 CMDB 比对

    Returns:
        扫描和比对结果
    """
    from app.core.config import settings

    celery_task_id = self.request.id

    async def _scheduled_scan():
        # 从配置读取待扫描网段列表
        subnets_str = settings.SCAN_SCHEDULED_SUBNETS.strip()
        subnets: list[str] = [s.strip() for s in subnets_str.split(",") if s.strip()]

        if not subnets:
            logger.info("定时扫描：未配置待扫描网段 (SCAN_SCHEDULED_SUBNETS)")
            return {
                "task_id": celery_task_id,
                "message": "未配置待扫描网段，请设置 SCAN_SCHEDULED_SUBNETS 环境变量",
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
                        result.task_id = celery_task_id
                        await scan_service.process_scan_result(db, scan_result=result, scan_task_id=celery_task_id)
                        total_hosts += result.hosts_found
                    scan_results.append(
                        {
                            "subnet": subnet,
                            "hosts_found": result.hosts_found,
                        }
                    )
                except Exception as e:
                    logger.error(f"定时扫描失败: {subnet}", error=str(e))
                    scan_results.append(
                        {
                            "subnet": subnet,
                            "error": str(e),
                        }
                    )

            # 比对 CMDB
            compare_result = await scan_service.compare_with_cmdb(db)

            return {
                "task_id": celery_task_id,
                "total_subnets": len(subnets),
                "total_hosts": total_hosts,
                "scan_results": scan_results,
                # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
                "compare_result": compare_result.model_dump(mode="json"),
            }

    return run_async(_scheduled_scan())


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.discovery.increment_offline_days",
    queue="discovery",
)
def increment_offline_days(self) -> dict[str, Any]:
    """
    增加发现记录的离线天数 (每日执行一次)

    Returns:
        更新结果
    """

    celery_task_id = self.request.id

    async def _increment():
        async with AsyncSessionLocal() as db:
            count = await discovery_crud.increment_offline_days(db)
            await db.commit()

            logger.info("离线天数更新完成", updated_count=count)

            return {
                "task_id": celery_task_id,
                "updated_count": count,
            }

    return run_async(_increment())
