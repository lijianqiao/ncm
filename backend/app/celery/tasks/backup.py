"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup.py
@DateTime: 2026-01-09 13:00:00
@Docs: 配置备份 Celery 任务 (Configuration Backup Celery Tasks).
"""

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
