"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: collect.py
@DateTime: 2026-01-09 22:30:00
@Docs: ARP/MAC 采集 Celery 任务 (ARP/MAC Collection Celery Tasks).

包含：
- 手动触发的采集任务
- Beat 调度的定时采集任务
"""

from typing import Any
from uuid import UUID

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async
from app.core.db import AsyncSessionLocal
from app.core.logger import celery_details_logger, celery_task_logger
from app.crud.crud_credential import credential as credential_crud
from app.crud.crud_device import device as device_crud
from app.schemas.collect import CollectBatchRequest
from app.services.collect_service import CollectService


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.collect.collect_device_tables",
    queue="discovery",
)
def collect_device_tables(self, device_id: str) -> dict[str, Any]:
    """
    采集单设备 ARP/MAC 表的 Celery 任务。

    Args:
        device_id: 设备ID（字符串格式）

    Returns:
        dict: 采集结果
    """
    celery_task_logger.info(f"开始采集设备: {device_id}")

    async def _collect():
        async with AsyncSessionLocal() as db:
            service = CollectService(db, device_crud, credential_crud)
            result = await service.collect_device(
                device_id=UUID(device_id),
                collect_arp=True,
                collect_mac=True,
            )
            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            return result.model_dump(mode="json")

    try:
        result = run_async(_collect())
        celery_task_logger.info(f"采集完成: device_id={device_id}, success={result.get('success')}")
        return result
    except Exception as e:
        celery_details_logger.error(f"采集异常: device_id={device_id}, error={str(e)}", exc_info=True)
        raise


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.collect.batch_collect_tables",
    queue="discovery",
)
def batch_collect_tables(
    self,
    device_ids: list[str],
    collect_arp: bool = True,
    collect_mac: bool = True,
    otp_code: str | None = None,
) -> dict[str, Any]:
    """
    批量采集设备 ARP/MAC 表的 Celery 任务。

    Args:
        device_ids: 设备ID列表（字符串格式）
        collect_arp: 是否采集 ARP
        collect_mac: 是否采集 MAC
        otp_code: OTP 验证码

    Returns:
        dict: 采集结果
    """
    celery_task_logger.info(f"开始批量采集: count={len(device_ids)}")

    async def _batch_collect():
        async with AsyncSessionLocal() as db:
            service = CollectService(db, device_crud, credential_crud)
            request = CollectBatchRequest(
                device_ids=[UUID(did) for did in device_ids],
                collect_arp=collect_arp,
                collect_mac=collect_mac,
                otp_code=otp_code,
            )
            result = await service.batch_collect(request)
            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            return result.model_dump(mode="json")

    try:
        result = run_async(_batch_collect())
        celery_task_logger.info(
            f"批量采集完成: total={result.get('total_devices')}, "
            f"success={result.get('success_count')}, failed={result.get('failed_count')}"
        )
        return result
    except Exception as e:
        celery_details_logger.error(f"批量采集异常: error={str(e)}", exc_info=True)
        raise


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.collect.scheduled_collect_all",
    queue="discovery",
)
def scheduled_collect_all(self) -> dict[str, Any]:
    """
    定时全量 ARP/MAC 采集任务（由 Celery Beat 调度）。

    采集所有活跃设备的 ARP/MAC 表。

    Returns:
        dict: 采集结果
    """
    celery_task_logger.info("定时采集任务开始")

    async def _collect_all():
        async with AsyncSessionLocal() as db:
            service = CollectService(db, device_crud, credential_crud)
            result = await service.collect_all_active_devices(
                collect_arp=True,
                collect_mac=True,
                concurrency=10,
            )
            # 使用 mode="json" 确保 datetime 等类型被序列化为 JSON 兼容格式
            return result.model_dump(mode="json")

    try:
        result = run_async(_collect_all())
        celery_task_logger.info(
            f"定时采集完成: total={result.get('total_devices')}, "
            f"success={result.get('success_count')}, failed={result.get('failed_count')}"
        )
        return result
    except Exception as e:
        celery_details_logger.error(f"定时采集异常: error={str(e)}", exc_info=True)
        raise
