"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-09 23:50:00
@Docs: 设备发现 Celery 任务 (Discovery Tasks).

包含网络扫描、CMDB 比对等异步任务。
支持并行扫描多网段以提升性能。
"""

import asyncio
from typing import Any, cast
from uuid import UUID

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async, safe_update_state
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.logger import celery_details_logger, celery_task_logger
from app.crud.crud_device import device as device_crud
from app.crud.crud_discovery import discovery_crud
from app.schemas.discovery import ScanResult as ScanResultSchema
from app.services.scan_service import ScanService

# 并行扫描最大并发数
SCAN_MAX_CONCURRENT = settings.SCAN_MAX_CONCURRENT


def _parse_snmp_cred_uuid(snmp_cred_id: str | None) -> "UUID | None":
    """解析 SNMP 凭据 UUID。

    Args:
        snmp_cred_id (str | None): SNMP 凭据 ID 字符串。

    Returns:
        UUID | None: 解析成功的 UUID 对象，失败或为空时返回 None。
    """
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
        self: Celery 任务实例。
        subnet (str): 网段 (CIDR 格式)。
        scan_type (str): 扫描类型 (nmap/masscan/auto)，默认为 auto。
        ports (str | None): 扫描端口，默认为 None。
        snmp_cred_id (str | None): SNMP 凭据 ID，默认为 None。

    Returns:
        dict[str, Any]: 扫描结果字典。
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
                celery_task_logger.info(
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
    批量扫描多个网段 Celery 任务（并行执行）。

    Args:
        self: Celery 任务实例。
        subnets (list[str]): 网段列表。
        scan_type (str): 扫描类型 (nmap/masscan/auto)，默认为 auto。
        ports (str | None): 扫描端口，默认为 None。
        snmp_cred_id (str | None): SNMP 凭据 ID，默认为 None。

    Returns:
        dict[str, Any]: 批量扫描结果字典。
    """

    celery_task_id = self.request.id
    snmp_cred_uuid = _parse_snmp_cred_uuid(snmp_cred_id)

    async def _batch_scan():
        """并行扫描多个网段。"""
        total = len(subnets) if subnets else 0
        if total == 0:
            return {
                "task_id": celery_task_id,
                "total_subnets": 0,
                "total_hosts": 0,
                "results": [],
            }

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(SCAN_MAX_CONCURRENT)
        # 跟踪已完成的扫描数
        completed_count = 0
        completed_lock = asyncio.Lock()

        async def scan_single_subnet(subnet: str) -> dict[str, Any]:
            """扫描单个网段（带并发控制）。"""
            nonlocal completed_count

            async with semaphore:
                try:
                    # 创建独立的 scan_service（避免并发问题）
                    scan_service = ScanService(
                        discovery_crud=discovery_crud,
                        device_crud=device_crud,
                    )

                    # 执行扫描
                    result = await _execute_scan(scan_service, subnet, scan_type, ports)

                    # 更新进度
                    async with completed_lock:
                        completed_count += 1
                        progress = int((completed_count / total) * 90)  # 保留 10% 给后续处理
                        safe_update_state(
                            self,
                            celery_task_id,
                            state="PROGRESS",
                            meta={
                                "progress": progress,
                                "stage": "scanning",
                                "completed": completed_count,
                                "total": total,
                                "current_subnet": subnet,
                                "hosts_found": result.hosts_found,
                            },
                        )

                    return {
                        "subnet": subnet,
                        "hosts_found": result.hosts_found,
                        "error": result.error,
                        "result": result,  # 保存完整结果用于后续处理
                    }
                except Exception as e:
                    celery_details_logger.error(f"扫描网段失败: {subnet}", error=str(e))
                    async with completed_lock:
                        completed_count += 1
                    return {
                        "subnet": subnet,
                        "hosts_found": 0,
                        "error": str(e),
                        "result": None,
                    }

        # 更新初始状态
        safe_update_state(
            self,
            celery_task_id,
            state="PROGRESS",
            meta={
                "progress": 0,
                "stage": "scanning",
                "total": total,
                "completed": 0,
                "message": f"并行扫描 {total} 个网段（最大并发: {SCAN_MAX_CONCURRENT}）",
            },
        )

        # 并行扫描所有网段
        scan_results = await asyncio.gather(
            *[scan_single_subnet(subnet) for subnet in subnets],
            return_exceptions=True,
        )

        # 处理扫描结果
        results = []
        total_hosts = 0

        safe_update_state(
            self,
            celery_task_id,
            state="PROGRESS",
            meta={"progress": 90, "stage": "processing", "total": total},
        )

        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            for scan_data in scan_results:
                # 处理 gather 返回的异常
                if isinstance(scan_data, Exception):
                    celery_details_logger.error("扫描任务异常", error=str(scan_data))
                    continue

                # 类型收窄：此时 scan_data 一定是 dict（使用 cast 帮助类型检查器）
                scan_dict = cast(dict[str, Any], scan_data)
                subnet = scan_dict.get("subnet", "unknown")
                result = scan_dict.get("result")

                results.append({
                    "subnet": subnet,
                    "hosts_found": scan_dict.get("hosts_found", 0),
                    "error": scan_dict.get("error"),
                })

                # 处理有效结果
                if result and result.hosts:
                    try:
                        result.task_id = celery_task_id
                        await scan_service.process_scan_result(
                            db,
                            scan_result=result,
                            scan_task_id=celery_task_id,
                            snmp_cred_id=snmp_cred_uuid,
                        )
                        total_hosts += result.hosts_found
                    except Exception as e:
                        celery_details_logger.error(f"处理扫描结果失败: {subnet}", error=str(e))

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

    Args:
        self: Celery 任务实例。

    Returns:
        dict[str, Any]: 比对结果字典。
    """

    async def _compare():
        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            result = await scan_service.compare_with_cmdb(db)

            celery_task_logger.info(
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
    定时网络扫描任务 (通过 Celery Beat 调度)。

    扫描预配置的网段列表，并与 CMDB 比对。
    使用统一的 _execute_scan 函数和并行扫描。

    Args:
        self: Celery 任务实例。

    Returns:
        dict[str, Any]: 扫描和比对结果字典。
    """

    celery_task_id = self.request.id

    async def _scheduled_scan():
        # 从配置读取待扫描网段列表
        subnets_str = settings.SCAN_SCHEDULED_SUBNETS.strip()
        subnets: list[str] = [s.strip() for s in subnets_str.split(",") if s.strip()]

        if not subnets:
            celery_task_logger.info("定时扫描：未配置待扫描网段 (SCAN_SCHEDULED_SUBNETS)")
            return {
                "task_id": celery_task_id,
                "message": "未配置待扫描网段，请设置 SCAN_SCHEDULED_SUBNETS 环境变量",
                "scanned": False,
            }

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(SCAN_MAX_CONCURRENT)
        total = len(subnets)

        async def scan_single_subnet(subnet: str) -> dict[str, Any]:
            """扫描单个网段（带并发控制），使用统一的 _execute_scan。"""
            async with semaphore:
                try:
                    scan_service = ScanService(
                        discovery_crud=discovery_crud,
                        device_crud=device_crud,
                    )
                    # 使用统一的 _execute_scan 函数
                    result = await _execute_scan(scan_service, subnet, "auto", None)
                    return {
                        "subnet": subnet,
                        "hosts_found": result.hosts_found,
                        "error": result.error,
                        "result": result,
                    }
                except Exception as e:
                    celery_details_logger.error(f"定时扫描失败: {subnet}", error=str(e))
                    return {
                        "subnet": subnet,
                        "hosts_found": 0,
                        "error": str(e),
                        "result": None,
                    }

        celery_task_logger.info(
            "定时扫描开始",
            total_subnets=total,
            max_concurrent=SCAN_MAX_CONCURRENT,
        )

        # 并行扫描所有网段
        scan_results_raw = await asyncio.gather(
            *[scan_single_subnet(subnet) for subnet in subnets],
            return_exceptions=True,
        )

        # 处理结果
        total_hosts = 0
        scan_results = []

        async with AsyncSessionLocal() as db:
            scan_service = ScanService(
                discovery_crud=discovery_crud,
                device_crud=device_crud,
            )

            for scan_data in scan_results_raw:
                # 处理 gather 返回的异常
                if isinstance(scan_data, Exception):
                    celery_details_logger.error("定时扫描任务异常", error=str(scan_data))
                    continue

                # 类型收窄：此时 scan_data 一定是 dict（使用 cast 帮助类型检查器）
                scan_dict = cast(dict[str, Any], scan_data)
                subnet = scan_dict.get("subnet", "unknown")
                result = scan_dict.get("result")

                scan_results.append({
                    "subnet": subnet,
                    "hosts_found": scan_dict.get("hosts_found", 0),
                    "error": scan_dict.get("error"),
                })

                # 处理有效结果
                if result and result.hosts:
                    try:
                        result.task_id = celery_task_id
                        await scan_service.process_scan_result(
                            db,
                            scan_result=result,
                            scan_task_id=celery_task_id,
                        )
                        total_hosts += result.hosts_found
                    except Exception as e:
                        celery_details_logger.error(f"处理定时扫描结果失败: {subnet}", error=str(e))

            # 比对 CMDB
            compare_result = await scan_service.compare_with_cmdb(db)

            celery_task_logger.info(
                "定时扫描完成",
                total_subnets=len(subnets),
                total_hosts=total_hosts,
            )

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
    增加发现记录的离线天数 (每日执行一次)。

    Args:
        self: Celery 任务实例。

    Returns:
        dict[str, Any]: 更新结果字典。
    """

    celery_task_id = self.request.id

    async def _increment():
        async with AsyncSessionLocal() as db:
            count = await discovery_crud.increment_offline_days(db)
            await db.commit()

            celery_task_logger.info("离线天数更新完成", updated_count=count)

            return {
                "task_id": celery_task_id,
                "updated_count": count,
            }

    return run_async(_increment())
