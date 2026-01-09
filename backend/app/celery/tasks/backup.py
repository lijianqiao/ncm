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

import asyncio
import difflib
import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.celery.app import celery_app
from app.celery.base import BaseTask
from app.core.db import AsyncSessionLocal
from app.core.enums import AlertSeverity, AlertType, AuthType, BackupStatus, BackupType, DeviceStatus
from app.core.logger import logger
from app.core.minio_client import put_text
from app.core.otp_service import otp_service
from app.crud.crud_alert import alert_crud
from app.crud.crud_backup import backup as backup_crud
from app.crud.crud_credential import credential as credential_crud
from app.models.backup import Backup
from app.models.device import Device
from app.network.nornir_config import init_nornir
from app.network.nornir_tasks import aggregate_results, backup_config
from app.schemas.alert import AlertCreate
from app.schemas.backup import BackupCreate
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService

# 存储阈值：小于 64KB 存 DB
CONTENT_SIZE_THRESHOLD = 64 * 1024


def _run_async(coro):
    """在同步 Celery 任务中运行异步代码。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 如果已有事件循环运行，创建新循环
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def _normalize_lines(text: str) -> list[str]:
    """差异预处理：去行尾空白、去空行。"""
    lines: list[str] = []
    for line in text.splitlines():
        s = line.rstrip()
        if not s:
            continue
        lines.append(s)
    return lines


def _compute_unified_diff(old_text: str, new_text: str, context_lines: int = 3) -> str:
    """计算 unified diff（用于告警详情）。"""
    old_lines = _normalize_lines(old_text)
    new_lines = _normalize_lines(new_text)
    diff_iter = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="old",
        tofile="new",
        lineterm="",
        n=context_lines,
    )
    return "\n".join(diff_iter)


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
            - device_id: 设备ID (可选，用于保存备份记录)
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

        # 保存备份结果到数据库
        _run_async(_save_backup_results(hosts_data, summary))

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


async def _save_backup_results(hosts_data: list[dict], summary: dict) -> None:
    """保存备份结果到数据库。"""
    async with AsyncSessionLocal() as db:
        for host in hosts_data:
            device_id = host.get("device_id")
            if not device_id:
                continue

            name = host.get("name", host.get("hostname"))
            result = summary.get("results", {}).get(name, {})
            status = result.get("status", "unknown")
            config_content = result.get("result") if status == "success" else None
            error_message = result.get("error") if status != "success" else None

            # 计算存储信息
            content = None
            content_path = None
            content_size = 0
            md5_hash = None

            if config_content:
                content_size = len(config_content.encode("utf-8"))
                md5_hash = hashlib.md5(config_content.encode("utf-8")).hexdigest()

                if content_size < CONTENT_SIZE_THRESHOLD:
                    content = config_content
                else:
                    # 存储到 MinIO
                    try:
                        object_name = f"backups/{device_id}/{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.txt"
                        await put_text(object_name, config_content)
                        content_path = object_name
                    except Exception as e:
                        # MinIO 不可用时降级存 DB（尽力而为）
                        content = config_content
                        logger.warning(f"大配置存 MinIO 失败，降级存 DB: {e}")

            try:
                from uuid import UUID

                backup_data = BackupCreate(
                    device_id=UUID(device_id),
                    backup_type=BackupType.MANUAL,
                    content=content,
                    content_path=content_path,
                    content_size=content_size,
                    md5_hash=md5_hash,
                    status=BackupStatus.SUCCESS if status == "success" else BackupStatus.FAILED,
                    error_message=error_message,
                )

                backup = Backup(**backup_data.model_dump())
                db.add(backup)
            except Exception as e:
                logger.error(f"保存备份记录失败: device_id={device_id}, error={e}")

        await db.commit()


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

    注意：
    - OTP_MANUAL 类型的设备会被跳过（需要人工输入 OTP）
    - OTP_SEED 类型的设备可以自动备份

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

    try:
        # 从数据库获取设备并准备备份数据
        hosts_data, skipped_devices = _run_async(_get_devices_for_scheduled_backup())

        if not hosts_data:
            result = {
                "task_id": task_id,
                "task_type": "scheduled_backup_all",
                "start_time": start_time.isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "status": "completed",
                "message": "没有可自动备份的设备",
                "total_devices": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": len(skipped_devices),
                "skipped_reason": "OTP_MANUAL 类型需要人工输入",
            }
            logger.info("定时备份: 没有可自动备份的设备", skipped=len(skipped_devices))
            return result

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "executing",
                "message": f"正在备份 {len(hosts_data)} 台设备...",
            },
        )

        # 初始化 Nornir 并执行备份
        nr = init_nornir(hosts_data, num_workers=min(50, len(hosts_data)))
        results = nr.run(task=backup_config)
        summary = aggregate_results(results)

        # 保存备份结果
        _run_async(_save_scheduled_backup_results(hosts_data, summary))

        end_time = datetime.now(UTC)
        result = {
            "task_id": task_id,
            "task_type": "scheduled_backup_all",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "status": "completed",
            "total_devices": len(hosts_data),
            "success_count": summary.get("success", 0),
            "failed_count": summary.get("failed", 0),
            "skipped_count": len(skipped_devices),
        }

        logger.info(
            "定时全量备份任务完成",
            task_id=task_id,
            success=summary.get("success", 0),
            failed=summary.get("failed", 0),
            skipped=len(skipped_devices),
            duration_seconds=result["duration_seconds"],
        )

        return result

    except Exception as e:
        logger.error(
            "定时全量备份任务失败",
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )
        raise


async def _get_devices_for_scheduled_backup() -> tuple[list[dict], list[str]]:
    """
    获取可自动备份的设备列表。

    Returns:
        tuple: (hosts_data, skipped_device_names)
        - hosts_data: Nornir 主机数据列表
        - skipped_device_names: 被跳过的设备名称列表（OTP_MANUAL 类型）
    """
    hosts_data = []
    skipped_devices = []

    async with AsyncSessionLocal() as db:
        # 获取所有活跃设备
        query = select(Device).where(Device.status == DeviceStatus.ACTIVE.value).where(Device.is_deleted.is_(False))
        result = await db.execute(query)
        devices = result.scalars().all()

        for device in devices:
            auth_type = AuthType(device.auth_type)

            # 跳过 OTP_MANUAL 类型（需要人工输入）
            if auth_type == AuthType.OTP_MANUAL:
                skipped_devices.append(device.name)
                continue

            try:
                # 获取凭据
                if auth_type == AuthType.STATIC:
                    if not device.username or not device.password_encrypted:
                        logger.warning(f"设备 {device.name} 缺少用户名或密码配置，跳过")
                        skipped_devices.append(device.name)
                        continue
                    credential = await otp_service.get_credential_for_static_device(
                        username=device.username,
                        encrypted_password=device.password_encrypted,
                    )
                elif auth_type == AuthType.OTP_SEED:
                    # 从 DeviceGroupCredential 获取
                    if not device.dept_id:
                        logger.warning(f"设备 {device.name} 缺少部门关联，跳过")
                        skipped_devices.append(device.name)
                        continue

                    cred = await credential_crud.get_by_dept_and_group(db, device.dept_id, device.device_group)
                    if not cred or not cred.otp_seed_encrypted:
                        logger.warning(f"设备 {device.name} 的凭据未配置 OTP 种子，跳过")
                        skipped_devices.append(device.name)
                        continue

                    credential = await otp_service.get_credential_for_otp_seed_device(
                        username=cred.username,
                        encrypted_seed=cred.otp_seed_encrypted,
                    )
                else:
                    skipped_devices.append(device.name)
                    continue

                hosts_data.append(
                    {
                        "name": device.name,
                        "hostname": device.ip_address,
                        "platform": device.vendor,
                        "username": credential.username,
                        "password": credential.password,
                        "port": device.ssh_port,
                        "device_id": str(device.id),
                    }
                )

            except Exception as e:
                logger.error(f"设备 {device.name} 凭据获取失败: {e}")
                skipped_devices.append(device.name)

    return hosts_data, skipped_devices


async def _save_scheduled_backup_results(hosts_data: list[dict], summary: dict) -> None:
    """保存定时备份结果到数据库。"""
    await _save_backup_results(hosts_data, summary)


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

    try:
        # 执行增量检查
        check_result = _run_async(_perform_incremental_check(self))

        end_time = datetime.now(UTC)
        result = {
            "task_id": task_id,
            "task_type": "incremental_backup_check",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "status": "completed",
            **check_result,
        }

        logger.info(
            "增量配置检查任务完成",
            task_id=task_id,
            total_checked=check_result.get("total_checked", 0),
            changed_count=check_result.get("changed_count", 0),
            duration_seconds=result["duration_seconds"],
        )

        return result

    except Exception as e:
        logger.error(
            "增量配置检查任务失败",
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )
        raise


async def _perform_incremental_check(task) -> dict[str, Any]:
    """
    执行增量配置检查。

    Returns:
        dict: 检查结果
    """
    from uuid import UUID

    total_checked = 0
    changed_count = 0
    backup_triggered = 0
    changed_devices = []

    async with AsyncSessionLocal() as db:
        # 获取可自动备份的设备
        hosts_data, _ = await _get_devices_for_scheduled_backup()

        if not hosts_data:
            return {
                "total_checked": 0,
                "changed_count": 0,
                "backup_triggered": 0,
                "message": "没有可检查的设备",
            }

        # 获取设备的最新备份信息（MD5 + 内容，用于差异与告警）
        device_ids = [UUID(h["device_id"]) for h in hosts_data if h.get("device_id")]
        old_info_map = await backup_crud.get_devices_latest_backup_info(db, device_ids)

        total_checked = len(hosts_data)

    # 分批检查配置变更（避免大量并发连接）
    batch_size = 10
    for i in range(0, len(hosts_data), batch_size):
        batch = hosts_data[i : i + batch_size]

        task.update_state(
            state="PROGRESS",
            meta={
                "stage": "checking",
                "message": f"正在检查配置变更 ({i + len(batch)}/{total_checked})...",
            },
        )

        # 初始化 Nornir 执行配置采集
        nr = init_nornir(batch, num_workers=min(10, len(batch)))
        results = nr.run(task=backup_config)
        summary = aggregate_results(results)

        # 对比 MD5
        for host in batch:
            device_id = host.get("device_id")
            if not device_id:
                continue

            name = host.get("name")
            result = summary.get("results", {}).get(name, {})

            if result.get("status") != "success":
                continue

            config = result.get("result")
            if not config:
                continue

            new_md5 = hashlib.md5(config.encode("utf-8")).hexdigest()
            old_info = old_info_map.get(UUID(device_id), {})
            old_md5 = old_info.get("md5_hash")
            old_backup_id = old_info.get("backup_id")
            old_content = old_info.get("content") or ""

            if old_md5 != new_md5:
                changed_count += 1
                changed_devices.append(
                    {
                        "device_id": device_id,
                        "device_name": name,
                        "old_md5": old_md5,
                        "new_md5": new_md5,
                    }
                )

                # 保存新备份
                async with AsyncSessionLocal() as db:
                    content_size = len(config.encode("utf-8"))
                    backup_data = BackupCreate(
                        device_id=UUID(device_id),
                        backup_type=BackupType.INCREMENTAL,
                        content=config if content_size < CONTENT_SIZE_THRESHOLD else None,
                        content_size=content_size,
                        md5_hash=new_md5,
                        status=BackupStatus.SUCCESS,
                    )
                    backup = Backup(**backup_data.model_dump())
                    db.add(backup)
                    await db.commit()
                    backup_triggered += 1

                    # 触发配置变更告警（写入 DB + 可选 Webhook）
                    try:
                        diff_text = ""
                        if old_content:
                            diff_text = _compute_unified_diff(old_content, config, context_lines=3)

                        alert_service = AlertService(db, alert_crud)
                        notification_service = NotificationService()
                        alert = await alert_service.create_alert(
                            AlertCreate(
                                alert_type=AlertType.CONFIG_CHANGE,
                                severity=AlertSeverity.MEDIUM,
                                title=f"设备配置变更: {name}",
                                message=f"检测到设备配置变更: {name}",
                                details={
                                    "device_id": str(device_id),
                                    "device_name": name,
                                    "old_backup_id": str(old_backup_id) if old_backup_id else None,
                                    "new_backup_id": str(backup.id),
                                    "old_md5": old_md5,
                                    "new_md5": new_md5,
                                    "diff": diff_text[:8000] if diff_text else "",
                                },
                                source="diff",
                                related_device_id=UUID(device_id),
                            )
                        )
                        await notification_service.send_webhook(alert)
                    except Exception as e:
                        logger.warning("配置变更告警触发失败", error=str(e))

    return {
        "total_checked": total_checked,
        "changed_count": changed_count,
        "backup_triggered": backup_triggered,
        "changed_devices": changed_devices[:10],  # 只返回前 10 个变更设备
    }
