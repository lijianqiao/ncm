"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup.py
@DateTime: 2026-01-09 13:00:00
@Docs: 配置备份 Celery 任务 (Configuration Backup Celery Tasks).

包含：
- 手动触发的备份任务
- Beat 调度的定时备份任务
"""

from datetime import UTC, datetime
from typing import Any

from app.celery.app import celery_app
from app.celery.base import BaseTask
from app.core.logger import logger
from app.network.nornir_config import init_nornir
from app.network.nornir_tasks import aggregate_results, backup_config


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.backup.backup_devices",
    queue="backup",
)
def backup_devices(self, hosts_data: list[dict[str, Any]], num_workers: int = 50) -> dict[str, Any]:
    """
    批量备份设备配置的 Celery 任务。

    Args:
        hosts_data: 主机数据列表，每个字典包含：
            - name: 设备名称
            - hostname: IP 地址
            - platform: 设备平台 (cisco_iosxe, huawei_vrp, hp_comware)
            - username: 登录用户名
            - password: 登录密码
            - port: SSH 端口 (可选，默认 22)
            - groups: 分组列表 (可选)
        num_workers: 并发 Worker 数量

    Returns:
        dict: 包含备份结果的字典
    """
    logger.info(
        "开始配置备份任务",
        task_id=self.request.id,
        hosts_count=len(hosts_data),
        num_workers=num_workers,
    )

    # 更新任务状态
    self.update_state(
        state="PROGRESS",
        meta={"stage": "initializing", "message": "正在初始化 Nornir..."},
    )

    try:
        # 初始化 Nornir
        nr = init_nornir(hosts_data, num_workers=num_workers)

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "executing",
                "message": f"正在备份 {len(nr.inventory.hosts)} 台设备...",
            },
        )

        # 执行备份
        results = nr.run(task=backup_config)

        # 聚合结果
        summary = aggregate_results(results)

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "completed",
                "message": f"备份完成: 成功 {summary['success']}, 失败 {summary['failed']}",
            },
        )

        logger.info(
            "配置备份任务完成",
            task_id=self.request.id,
            success=summary["success"],
            failed=summary["failed"],
        )

        return summary

    except Exception as e:
        logger.error(
            "配置备份任务失败",
            task_id=self.request.id,
            error=str(e),
            exc_info=True,
        )
        raise


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.backup.backup_single_device",
    queue="backup",
)
def backup_single_device(
    self,
    hostname: str,
    platform: str,
    username: str,
    password: str,
    port: int = 22,
    device_name: str | None = None,
) -> dict[str, Any]:
    """
    备份单台设备配置的 Celery 任务。

    Args:
        hostname: 设备 IP 地址或主机名
        platform: 设备平台
        username: 登录用户名
        password: 登录密码
        port: SSH 端口
        device_name: 设备名称 (可选)

    Returns:
        dict: 包含备份结果的字典
    """
    name = device_name or hostname

    logger.info(
        "开始单设备备份",
        task_id=self.request.id,
        device=name,
        hostname=hostname,
    )

    hosts_data = [
        {
            "name": name,
            "hostname": hostname,
            "platform": platform,
            "username": username,
            "password": password,
            "port": port,
        }
    ]

    try:
        nr = init_nornir(hosts_data, num_workers=1)
        results = nr.run(task=backup_config)
        summary = aggregate_results(results)

        # 提取单设备结果
        device_result = summary["results"].get(name, {})

        return {
            "device": name,
            "hostname": hostname,
            "status": device_result.get("status", "unknown"),
            "config": device_result.get("result") if device_result.get("status") == "success" else None,
            "error": device_result.get("error"),
        }

    except Exception as e:
        logger.error(
            "单设备备份失败",
            task_id=self.request.id,
            device=name,
            error=str(e),
            exc_info=True,
        )
        raise


# ===== Celery Beat 定时任务 =====


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.backup.scheduled_backup_all",
    queue="backup",
)
def scheduled_backup_all(self) -> dict[str, Any]:
    """
    定时全量配置备份任务（由 Celery Beat 调度）。

    该任务会从数据库获取所有需要备份的设备，执行批量备份。
    典型配置：每日凌晨 2:00 执行。

    Returns:
        dict: 备份结果摘要
    """
    task_id = self.request.id
    start_time = datetime.now(UTC)

    logger.info(
        "定时全量备份任务开始",
        task_id=task_id,
        scheduled_time=start_time.isoformat(),
    )

    self.update_state(
        state="PROGRESS",
        meta={"stage": "fetching_devices", "message": "正在获取设备列表..."},
    )

    # TODO: Phase 1 实现 - 从数据库获取所有活跃设备
    # devices = await device_service.get_active_devices()
    # hosts_data = [device.to_nornir_host() for device in devices]

    # 当前为占位实现，返回空结果
    result = {
        "task_id": task_id,
        "task_type": "scheduled_backup_all",
        "start_time": start_time.isoformat(),
        "end_time": datetime.now(UTC).isoformat(),
        "status": "completed",
        "message": "定时备份任务已执行（设备服务待实现）",
        "total_devices": 0,
        "success_count": 0,
        "failed_count": 0,
    }

    logger.info(
        "定时全量备份任务完成",
        task_id=task_id,
        duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
    )

    return result


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.backup.incremental_backup_check",
    queue="backup",
)
def incremental_backup_check(self) -> dict[str, Any]:
    """
    定时增量配置检查任务（由 Celery Beat 调度）。

    该任务会检查设备配置是否发生变更：
    1. 获取上次备份的配置 MD5
    2. 采集当前配置并计算 MD5
    3. 对比发现变更的设备进行增量备份
    4. 变更设备触发告警通知

    典型配置：每 4 小时执行一次。

    Returns:
        dict: 检查结果摘要
    """
    task_id = self.request.id
    start_time = datetime.now(UTC)

    logger.info(
        "增量配置检查任务开始",
        task_id=task_id,
        scheduled_time=start_time.isoformat(),
    )

    self.update_state(
        state="PROGRESS",
        meta={"stage": "checking", "message": "正在检查配置变更..."},
    )

    # TODO: Phase 1 实现 - 增量检查逻辑
    # 1. 获取所有设备的最新备份 MD5
    # 2. 采集当前配置
    # 3. 对比 MD5，发现变更
    # 4. 变更设备执行增量备份
    # 5. 生成变更告警

    result = {
        "task_id": task_id,
        "task_type": "incremental_backup_check",
        "start_time": start_time.isoformat(),
        "end_time": datetime.now(UTC).isoformat(),
        "status": "completed",
        "message": "增量检查任务已执行（检查逻辑待实现）",
        "total_checked": 0,
        "changed_count": 0,
        "backup_triggered": 0,
    }

    logger.info(
        "增量配置检查任务完成",
        task_id=task_id,
        duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
    )

    return result
