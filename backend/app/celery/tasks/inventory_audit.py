"""
@Author: li
@Email: lij
@FileName: inventory_audit.py
@DateTime: 2026-01-09 21:35:00
@Docs: 资产盘点 Celery 任务。
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.enums import InventoryAuditStatus
from app.core.logger import logger
from app.crud.crud_device import device as device_crud
from app.crud.crud_discovery import discovery_crud
from app.models.device import Device
from app.models.discovery import Discovery
from app.models.inventory_audit import InventoryAudit
from app.services.scan_service import ScanService


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.inventory_audit.run_inventory_audit",
    queue="discovery",
)
def run_inventory_audit(self, audit_id: str) -> dict[str, Any]:
    """执行资产盘点任务（复用 Nmap 扫描 + Discovery/CMDB 比对）。"""
    logger.info("开始资产盘点任务", task_id=self.request.id, audit_id=audit_id)
    return run_async(_run_inventory_audit_async(self, audit_id))


async def _run_inventory_audit_async(self, audit_id: str) -> dict[str, Any]:
    service = ScanService(discovery_crud, device_crud)

    async with AsyncSessionLocal() as db:
        audit_uuid = UUID(audit_id)
        # 使用 refresh 获取最新数据（API 层已通过 bind_celery_task 更新了 status 和 started_at）
        audit = await db.get(InventoryAudit, audit_uuid)
        if not audit:
            raise ValueError("盘点任务不存在")
        # 刷新获取最新的 version_id，避免乐观锁冲突
        await db.refresh(audit)

        # scope 解析（强类型约定：subnets/dept_id/device_ids）
        scope = audit.scope or {}
        subnets: list[str] = list(scope.get("subnets") or [])
        dept_id = scope.get("dept_id")
        device_ids = scope.get("device_ids") or []
        ports = scope.get("ports")

        # 如果提供 dept_id/device_ids，则补充扫描目标（按设备 IP 生成 /32）
        try:
            targets: list[str] = []
            if dept_id:
                rows = (await db.execute(select(Device.ip_address).where(Device.dept_id == UUID(str(dept_id))))).all()
                targets.extend([f"{ip}/32" for (ip,) in rows if ip])
            if device_ids:
                ids = [UUID(str(x)) for x in device_ids]
                rows = (await db.execute(select(Device.ip_address).where(Device.id.in_(ids)))).all()
                targets.extend([f"{ip}/32" for (ip,) in rows if ip])
            # 合并到 subnets 列表（去重）
            if targets:
                subnets = list(dict.fromkeys(subnets + targets))
        except Exception as e:
            logger.warning("根据 dept_id/device_ids 生成扫描目标失败", error=str(e))

        processed_hosts = 0
        scan_errors: list[str] = []

        # 1) 并发执行 Nmap 扫描（使用 Semaphore 控制最大并发数）
        semaphore = asyncio.Semaphore(settings.SCAN_MAX_CONCURRENT_SUBNETS)
        scan_results_map: dict[str, Any] = {}  # subnet -> ScanResult

        async def scan_subnet(subnet: str) -> tuple[str, Any, str | None]:
            """扫描单个子网，返回 (subnet, ScanResult, 错误信息)"""
            async with semaphore:
                try:
                    logger.info("开始扫描子网", subnet=subnet, audit_id=audit_id)
                    scan_result = await service.nmap_scan(subnet=subnet, ports=ports)
                    logger.info(
                        "子网扫描完成",
                        subnet=subnet,
                        hosts_found=scan_result.hosts_found,
                    )
                    return subnet, scan_result, None
                except Exception as e:
                    logger.error("子网扫描失败", subnet=subnet, error=str(e))
                    return subnet, None, f"{subnet}: {e}"

        # 并发执行所有子网扫描
        if subnets:
            results = await asyncio.gather(*[scan_subnet(s) for s in subnets])
            for subnet, scan_result, error in results:
                if error:
                    scan_errors.append(error)
                elif scan_result:
                    scan_results_map[subnet] = scan_result

        # 2) 串行写入数据库（避免并发写入冲突）
        for subnet, scan_result in scan_results_map.items():
            try:
                count = await service.process_scan_result(
                    db=db, scan_result=scan_result, scan_task_id=str(audit.id)
                )
                processed_hosts += count
            except Exception as e:
                logger.error("处理扫描结果失败", subnet=subnet, error=str(e))
                scan_errors.append(f"{subnet} (处理): {e}")

        # 2) CMDB 比对：产出 shadow/matched
        try:
            compare_result = await service.compare_with_cmdb(db=db)
        except Exception as e:
            compare_result = None
            scan_errors.append(f"compare_with_cmdb: {e}")

        # 3) 汇总统计（仅统计本次 audit_id 写入的 discovery）
        base_q = select(Discovery).where(Discovery.scan_task_id == str(audit.id))
        total = await db.scalar(select(func.count()).select_from(base_q.subquery())) or 0

        by_status_stmt = (
            select(Discovery.status, func.count(Discovery.id))
            .where(Discovery.scan_task_id == str(audit.id))
            .group_by(Discovery.status)
        )
        rows = (await db.execute(by_status_stmt)).all()
        by_status = {str(k): int(v) for k, v in rows}

        result = {
            "subnets": subnets,
            "processed_hosts": processed_hosts,
            "discoveries_total": int(total),
            "discoveries_by_status": by_status,
            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            "cmdb_compare": compare_result.model_dump(mode="json") if compare_result else None,
            "errors": scan_errors,
        }

        audit.result = result
        # 根据结果判断状态：无错误=SUCCESS，部分成功=PARTIAL，全部失败=FAILED
        if not scan_errors:
            audit.status = InventoryAuditStatus.SUCCESS.value
        elif processed_hosts > 0:
            audit.status = InventoryAuditStatus.PARTIAL.value
        else:
            audit.status = InventoryAuditStatus.FAILED.value
        audit.finished_at = datetime.now(UTC)
        audit.error_message = "\n".join(scan_errors) if scan_errors else None
        await db.flush()
        await db.commit()

        return {"status": audit.status, "result": result}
