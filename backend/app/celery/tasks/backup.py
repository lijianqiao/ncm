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
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async, safe_update_state, safe_update_state_async
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.enums import AlertSeverity, AlertType, AuthType, BackupStatus, BackupType, DeviceStatus
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.core.minio_client import delete_object, put_text
from app.core.otp_service import otp_service
from app.crud.crud_alert import alert_crud
from app.crud.crud_backup import backup as backup_crud
from app.crud.crud_credential import credential as credential_crud
from app.models.backup import Backup
from app.models.device import Device
from app.schemas.alert import AlertCreate
from app.schemas.backup import BackupCreate
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService
from app.utils.validators import compute_text_md5, should_skip_backup_save_due_to_unchanged_md5

# 备份类型与保留数量的映射（懒加载，避免模块导入时 settings 未初始化）
_BACKUP_RETENTION_MAP: dict[BackupType, str] | None = None


def _get_keep_count(bt: BackupType) -> int:
    """根据备份类型获取保留数量（使用字典映射替代 if-elif）。"""
    global _BACKUP_RETENTION_MAP
    if _BACKUP_RETENTION_MAP is None:
        _BACKUP_RETENTION_MAP = {
            BackupType.SCHEDULED: "BACKUP_RETENTION_SCHEDULED_KEEP",
            BackupType.MANUAL: "BACKUP_RETENTION_MANUAL_KEEP",
            BackupType.PRE_CHANGE: "BACKUP_RETENTION_PRE_CHANGE_KEEP",
            BackupType.POST_CHANGE: "BACKUP_RETENTION_POST_CHANGE_KEEP",
            BackupType.INCREMENTAL: "BACKUP_RETENTION_INCREMENTAL_KEEP",
        }

    attr_name = _BACKUP_RETENTION_MAP.get(bt)
    if attr_name is None:
        return 0
    return getattr(settings, attr_name, 0)


async def _enforce_retention_for_device(db: Any, device_id: str) -> None:
    """按条数+按天数清理备份，保证每台设备至少保留 1 条（优先保留最新成功备份）。"""
    did = UUID(device_id)
    keep_ids: set[UUID] = set()

    latest_any_q = (
        select(Backup.id)
        .where(Backup.device_id == did)
        .where(Backup.is_deleted.is_(False))
        .order_by(Backup.created_at.desc())
        .limit(1)
    )
    latest_any = await db.execute(latest_any_q)
    latest_any_id = latest_any.scalar()
    if latest_any_id:
        keep_ids.add(latest_any_id)

    latest_success_q = (
        select(Backup.id)
        .where(Backup.device_id == did)
        .where(Backup.is_deleted.is_(False))
        .where(Backup.status == BackupStatus.SUCCESS.value)
        .order_by(Backup.created_at.desc())
        .limit(1)
    )
    latest_success = await db.execute(latest_success_q)
    latest_success_id = latest_success.scalar()
    if latest_success_id:
        keep_ids.add(latest_success_id)

    to_delete: dict[UUID, Backup] = {}

    # 1) 按条数（按类型、仅成功备份；失败备份交给按天数清理）
    for bt in BackupType:
        keep = _get_keep_count(bt)
        if keep <= 0:
            continue

        q = (
            select(Backup)
            .where(Backup.device_id == did)
            .where(Backup.is_deleted.is_(False))
            .where(Backup.status == BackupStatus.SUCCESS.value)
            .where(Backup.backup_type == bt.value)
            .order_by(Backup.created_at.desc())
            .offset(keep)
        )
        r = await db.execute(q)
        for b in r.scalars().all():
            if b.id in keep_ids:
                continue
            to_delete[b.id] = b

    # 2) 按天数（所有备份类型）
    keep_days = settings.BACKUP_RETENTION_KEEP_DAYS
    if keep_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=keep_days)
        q = (
            select(Backup)
            .where(Backup.device_id == did)
            .where(Backup.is_deleted.is_(False))
            .where(Backup.created_at < cutoff)
        )
        r = await db.execute(q)
        for b in r.scalars().all():
            if b.id in keep_ids:
                continue
            to_delete[b.id] = b

    if not to_delete:
        return

    for b in to_delete.values():
        if b.content_path:
            try:
                await delete_object(b.content_path)
            except Exception as e:
                logger.warning("MinIO 删除对象失败", path=b.content_path, error=str(e))
        b.is_deleted = True
        db.add(b)


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


def _convert_async_results_to_summary(results) -> dict:
    """
    将 AsyncRunner 结果转换为 aggregate_results 兼容的格式。

    Args:
        results: AsyncRunner 返回的 AggregatedResult

    Returns:
        dict: 兼容 _save_backup_results 的格式
            {"results": {name: {"status": ..., "result": ..., "error": ...}}, "success": n, "failed": n}
    """
    summary: dict = {"results": {}, "success": 0, "failed": 0}

    for host_name, multi_result in results.items():
        if multi_result.failed:
            exc = multi_result[0].exception if multi_result else None
            summary["results"][host_name] = {
                "status": "failed",
                "result": None,
                "error": str(exc) if exc else "Unknown error",
            }
            summary["failed"] += 1
        else:
            result_data = multi_result[0].result if multi_result else None
            if result_data and result_data.get("success"):
                summary["results"][host_name] = {
                    "status": "success",
                    "result": result_data.get("config"),
                    "error": None,
                }
                summary["success"] += 1
            else:
                summary["results"][host_name] = {
                    "status": "failed",
                    "result": None,
                    "error": result_data.get("error") if result_data else "Unknown error",
                }
                summary["failed"] += 1

    return summary


async def _save_backup_results(
    hosts_data: list[dict],
    summary: dict,
    backup_type: str = BackupType.MANUAL.value,
    operator_id: str | None = None,
) -> None:
    """保存备份结果到数据库（支持指定备份类型、md5 去重、保留策略）。"""
    async with AsyncSessionLocal() as db:
        try:
            bt = BackupType(backup_type)
        except Exception:
            bt = BackupType.MANUAL

        for host in hosts_data:
            device_id = host.get("device_id")
            if not device_id:
                continue

            effective_operator_id = operator_id or host.get("operator_id")

            name = host.get("name", host.get("hostname"))
            result = summary.get("results", {}).get(name, {})
            status = result.get("status", "unknown")
            error_message = result.get("error") if status != "success" else None
            if status == "otp_required" or (
                error_message
                and "otp" in error_message.lower()
                and ("过期" in error_message or "required" in error_message.lower() or "认证" in error_message)
            ):
                logger.info(
                    "OTP 过期导致备份暂停，跳过记录",
                    device_id=device_id,
                    device_name=name,
                )
                continue
            config_content = result.get("result") if status == "success" else None

            # 计算存储信息
            content = None
            content_path = None
            content_size = 0
            md5_hash = None

            if config_content:
                content_size = len(config_content.encode("utf-8"))
                md5_hash = compute_text_md5(config_content)

                # md5 去重：仅对 pre/post 变更备份生效
                if bt in {BackupType.PRE_CHANGE, BackupType.POST_CHANGE}:
                    try:
                        old_md5 = await backup_crud.get_latest_md5_by_device(db, UUID(device_id))
                        if should_skip_backup_save_due_to_unchanged_md5(
                            backup_type=bt.value,
                            status=BackupStatus.SUCCESS.value,
                            old_md5=old_md5,
                            new_md5=md5_hash,
                        ):
                            logger.info(
                                "备份内容未变化，跳过保存",
                                device_id=device_id,
                                backup_type=bt.value,
                                md5=md5_hash,
                            )
                            continue
                    except Exception as e:
                        logger.warning(
                            "md5 去重检查失败，继续保存",
                            device_id=device_id,
                            error=str(e),
                        )

                if content_size < settings.BACKUP_CONTENT_SIZE_THRESHOLD_BYTES:
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
                        logger.warning("大配置存 MinIO 失败，降级存 DB", device_id=device_id, error=str(e))

            try:
                backup_data = BackupCreate(
                    device_id=UUID(device_id),
                    backup_type=bt,
                    content=content,
                    content_path=content_path,
                    content_size=content_size,
                    md5_hash=md5_hash,
                    status=BackupStatus.SUCCESS if status == "success" else BackupStatus.FAILED,
                    error_message=error_message,
                    operator_id=UUID(str(effective_operator_id)) if effective_operator_id else None,
                )

                backup = Backup(**backup_data.model_dump())
                db.add(backup)
            except Exception as e:
                logger.error("保存备份记录失败", device_id=device_id, error=str(e))

        await db.commit()

        # 保留策略清理：按条数（各类型可配）+ 按天数（默认 7 天），每台设备至少保留 1 条（优先最新成功）
        unique_device_ids: list[str] = sorted({str(h["device_id"]) for h in hosts_data if h.get("device_id")})
        for did in unique_device_ids:
            try:
                await _enforce_retention_for_device(db, did)
            except Exception as e:
                logger.warning("备份保留策略清理失败", device_id=did, error=str(e))

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
        from app.network.async_runner import run_async_tasks
        from app.network.async_tasks import async_collect_config
        from app.network.nornir_config import init_nornir_async

        # 添加必要的 data 字段
        hosts_data[0]["data"] = {"device_id": name, "device_name": name}

        inventory = init_nornir_async(hosts_data)
        results = run_async(
            run_async_tasks(
                inventory.hosts,
                async_collect_config,
                num_workers=1,
            )
        )

        # 提取单设备结果
        multi_result = results.get(name)
        if multi_result and not multi_result.failed:
            result_data = multi_result[0].result if multi_result else None
            if result_data and result_data.get("success"):
                return {
                    "device": name,
                    "hostname": hostname,
                    "status": "success",
                    "config": result_data.get("config"),
                    "error": None,
                }

        error_msg = None
        if multi_result and multi_result.failed:
            error_msg = str(multi_result[0].exception) if multi_result else "Unknown error"

        return {
            "device": name,
            "hostname": hostname,
            "status": "failed",
            "config": None,
            "error": error_msg,
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
        hosts_data, skipped_devices = run_async(_get_devices_for_scheduled_backup())

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

        from app.network.async_runner import run_async_tasks
        from app.network.async_tasks import async_collect_config
        from app.network.nornir_config import init_nornir_async

        inventory = init_nornir_async(hosts_data)
        results = run_async(
            run_async_tasks(
                inventory.hosts,
                async_collect_config,
                num_workers=min(50, len(hosts_data)),
            )
        )

        # 转换异步结果格式以兼容 _save_backup_results
        summary = _convert_async_results_to_summary(results)

        run_async(
            _save_backup_results(
                hosts_data,
                summary,
                backup_type=BackupType.SCHEDULED.value,
                operator_id=None,
            )
        )

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
                        logger.warning("设备缺少用户名或密码配置，跳过", device_name=device.name)
                        skipped_devices.append(device.name)
                        continue
                    credential = await otp_service.get_credential_for_static_device(
                        username=device.username,
                        encrypted_password=device.password_encrypted,
                    )
                    username = credential.username
                    password = credential.password
                    extra_data = {
                        "auth_type": "static",
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "vendor": device.vendor,
                    }
                elif auth_type == AuthType.OTP_SEED:
                    # 从 DeviceGroupCredential 获取
                    if not device.dept_id:
                        logger.warning("设备缺少部门关联，跳过", device_name=device.name)
                        skipped_devices.append(device.name)
                        continue

                    cred = await credential_crud.get_by_dept_and_group(db, device.dept_id, device.device_group)
                    if not cred or not cred.otp_seed_encrypted:
                        logger.warning("设备的凭据未配置 OTP 种子，跳过", device_name=device.name)
                        skipped_devices.append(device.name)
                        continue
                    username = cred.username
                    password = ""
                    extra_data = {
                        "auth_type": "otp_seed",
                        "otp_seed_encrypted": cred.otp_seed_encrypted,
                        "dept_id": str(device.dept_id),
                        "device_group": str(device.device_group),
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "vendor": device.vendor,
                    }
                else:
                    skipped_devices.append(device.name)
                    continue

                hosts_data.append(
                    {
                        "name": device.name,
                        "hostname": device.ip_address,
                        "platform": device.platform or device.vendor,
                        "username": username,
                        "password": password,
                        "port": device.ssh_port,
                        "device_id": str(device.id),
                        "data": extra_data,
                    }
                )

            except Exception as e:
                logger.error("设备凭据获取失败", device_name=device.name, error=str(e))
                skipped_devices.append(device.name)

    return hosts_data, skipped_devices


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

    safe_update_state(
        self,
        task_id,
        state="PROGRESS",
        meta={"stage": "checking", "message": "正在检查配置变更..."},
    )

    try:
        # 执行增量检查
        check_result = run_async(_perform_incremental_check(self, task_id))

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


async def _perform_incremental_check(task, celery_task_id: str | None) -> dict[str, Any]:
    """
    执行增量配置检查。

    Returns:
        dict: 检查结果
    """
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

        safe_update_state(
            task,
            celery_task_id,
            state="PROGRESS",
            meta={
                "stage": "checking",
                "message": f"正在检查配置变更 ({i + len(batch)}/{total_checked})...",
            },
        )

        from app.network.async_runner import run_async_tasks
        from app.network.async_tasks import async_collect_config
        from app.network.nornir_config import init_nornir_async

        inventory = init_nornir_async(batch)
        results = await run_async_tasks(
            inventory.hosts,
            async_collect_config,
            num_workers=min(10, len(batch)),
        )
        summary = _convert_async_results_to_summary(results)

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

            new_md5 = compute_text_md5(config)
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
                        "config": config,
                        "old_content": old_content,
                        "old_backup_id": old_backup_id,
                    }
                )

    # 批量保存变更设备的备份（使用单个 Session，减少数据库连接开销）
    if changed_devices:
        async with AsyncSessionLocal() as db:
            for device_info in changed_devices:
                device_id = device_info["device_id"]
                name = device_info["device_name"]
                config = device_info["config"]
                old_content = device_info["old_content"]
                old_backup_id = device_info["old_backup_id"]
                new_md5 = device_info["new_md5"]
                old_md5 = device_info["old_md5"]

                content_size = len(config.encode("utf-8"))

                # 处理大配置：存储到 MinIO
                content = None
                content_path = None
                if content_size < settings.BACKUP_CONTENT_SIZE_THRESHOLD_BYTES:
                    content = config
                else:
                    try:
                        object_name = f"backups/{device_id}/{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.txt"
                        await put_text(object_name, config)
                        content_path = object_name
                    except Exception as e:
                        # MinIO 不可用时降级存 DB
                        content = config
                        logger.warning("大配置存 MinIO 失败，降级存 DB", device_id=device_id, error=str(e))

                backup_data = BackupCreate(
                    device_id=UUID(device_id),
                    backup_type=BackupType.INCREMENTAL,
                    content=content,
                    content_path=content_path,
                    content_size=content_size,
                    md5_hash=new_md5,
                    status=BackupStatus.SUCCESS,
                )
                backup = Backup(**backup_data.model_dump())
                db.add(backup)
                await db.flush()
                await db.refresh(backup)
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

            await db.commit()

    return {
        "total_checked": total_checked,
        "changed_count": changed_count,
        "backup_triggered": backup_triggered,
        "changed_devices": changed_devices[:10],  # 只返回前 10 个变更设备
    }


# ===== 异步版本备份任务 (Phase 3 - AsyncRunner) =====


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.backup.async_backup_devices",
    queue="backup",
)
def async_backup_devices(
    self,
    hosts_data: list[dict[str, Any]],
    num_workers: int = 100,
    backup_type: str = BackupType.MANUAL.value,
    operator_id: str | None = None,
) -> dict[str, Any]:
    """
    异步批量备份设备配置的 Celery 任务。

    使用 AsyncRunner + Scrapli Async 实现真正的异步并发，
    相比 ThreadedRunner 显著降低资源开销。

    Args:
        hosts_data: 主机数据列表
        num_workers: 最大并发连接数（默认 100）
        backup_type: 备份类型

    Returns:
        dict: 包含备份结果的字典
    """
    from app.network.async_runner import run_async_tasks
    from app.network.async_tasks import async_collect_config
    from app.network.nornir_config import init_nornir_async

    logger.info(
        "开始异步配置备份任务",
        task_id=self.request.id,
        hosts_count=len(hosts_data),
        num_workers=num_workers,
        backup_type=backup_type,
    )

    total_hosts = len(hosts_data)

    self.update_state(
        state="PROGRESS",
        meta={
            "stage": "initializing",
            "message": "正在初始化异步 Inventory...",
            "completed": 0,
            "total": total_hosts,
        },
    )

    try:
        # 初始化异步 Inventory
        inventory = init_nornir_async(hosts_data)

        total_hosts = len(inventory.hosts)  # 更新为实际 inventory 数量
        progress_lock = asyncio.Lock()
        completed = 0
        name_to_id = {h.get("name"): h.get("device_id") for h in hosts_data if h.get("name")}
        otp_notice_sent = False

        # 关键：在主线程中预先获取 task_id，避免在后台线程中访问 self.request
        celery_task_id = self.request.id
        celery_task = self

        async def _progress_callback(host_name: str, _result: Any) -> None:
            nonlocal completed
            nonlocal otp_notice_sent

            otp_meta: dict[str, Any] | None = None
            if _result.exception and isinstance(_result.exception, OTPRequiredException):
                otp_notice_sent = True
                device_id = name_to_id.get(host_name)
                otp_exc = _result.exception
                otp_meta = {
                    "otp_required": True,
                    "otp_dept_id": str(otp_exc.dept_id),
                    "otp_device_group": otp_exc.device_group,
                    "otp_failed_device_ids": [str(device_id)] if device_id else [],
                }
                await safe_update_state_async(
                    celery_task,
                    celery_task_id,
                    state="PROGRESS",
                    meta={
                        "stage": "otp_required",
                        "message": "需要重新输入 OTP 验证码",
                        "completed": completed,
                        "total": total_hosts,
                        **otp_meta,
                    },
                )

            async with progress_lock:
                completed += 1
                progress_meta = {
                    "stage": "executing",
                    "message": f"已完成 {completed}/{total_hosts}",
                    "completed": completed,
                    "total": total_hosts,
                }
                if otp_notice_sent:
                    progress_meta["otp_required"] = True
                if otp_meta:
                    progress_meta.update(otp_meta)

                logger.debug(
                    "进度回调触发",
                    task_id=celery_task_id,
                    host=host_name,
                    completed=completed,
                    total=total_hosts,
                )

                await safe_update_state_async(
                    celery_task,
                    celery_task_id,
                    state="PROGRESS",
                    meta=progress_meta,
                )

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "executing",
                "message": f"正在异步备份 {total_hosts} 台设备...",
                "completed": 0,
                "total": total_hosts,
            },
        )

        results = run_async(
            run_async_tasks(
                inventory.hosts,
                async_collect_config,
                num_workers=num_workers,
                progress_callback=_progress_callback,
                otp_wait_timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
            )
        )

        # 聚合结果（转换为与同步版本兼容的格式）
        summary = _aggregate_async_results(results, hosts_data)

        # 保存备份结果到数据库
        run_async(
            _save_backup_results(
                hosts_data,
                summary,
                backup_type=backup_type,
                operator_id=operator_id,
            )
        )

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "completed",
                "message": f"异步备份完成: 成功 {summary['success']}, 失败 {summary['failed']}",
                "completed": summary["total"],
                "total": summary["total"],
            },
        )

        logger.info(
            "异步配置备份任务完成",
            task_id=self.request.id,
            success=summary["success"],
            failed=summary["failed"],
        )

        return summary

    except Exception as e:
        logger.error(
            "异步配置备份任务失败",
            task_id=self.request.id,
            error=str(e),
            exc_info=True,
        )
        raise


def _aggregate_async_results(
    results: Any,
    hosts_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    聚合 AsyncRunner 结果为与同步版本兼容的格式。

    支持 OTP 超时检测：当有设备因 OTP 等待超时而失败时，
    在返回结果中标记 otp_timeout 状态。

    Args:
        results: AsyncRunner 返回的 AggregatedResult
        hosts_data: 原始主机数据

    Returns:
        dict: 兼容格式的聚合结果
    """
    success_count = 0
    failed_count = 0
    results_dict: dict[str, dict[str, Any]] = {}
    otp_required_info: dict[str, Any] | None = None
    otp_failed_device_ids: list[str] = []
    otp_timeout_device_ids: list[str] = []
    completed_device_ids: list[str] = []
    skipped_device_ids: list[str] = []

    # 构建 device_id -> name 映射
    id_to_name = {h.get("name"): h.get("name") for h in hosts_data}
    name_to_id = {h.get("name"): h.get("device_id") for h in hosts_data if h.get("name") and h.get("device_id")}
    for h in hosts_data:
        if h.get("device_id"):
            id_to_name[h.get("device_id")] = h.get("name")

    # 记录原始数据用于调试
    logger.debug(
        "开始聚合异步结果",
        hosts_count=len(hosts_data),
        results_count=len(results) if results else 0,
    )

    for host_name, multi_result in results.items():
        # 尝试映射回设备名
        name = id_to_name.get(host_name) or host_name
        device_id = name_to_id.get(name)

        # multi_result 是 MultiResult，取第一个 Result
        if not multi_result or multi_result.failed:
            failed_count += 1
            error_msg = "执行失败"
            otp_required: OTPRequiredException | None = None
            is_otp_timeout = False

            if multi_result and len(multi_result) > 0:
                r = multi_result[0]
                result_data = r.result or {}

                # 检查是否为 OTP 超时
                if result_data.get("otp_timeout"):
                    is_otp_timeout = True
                    error_msg = result_data.get("error", "等待 OTP 超时")
                    if device_id:
                        otp_timeout_device_ids.append(str(device_id))
                    # 检查是否为跳过的设备（超时后未执行）
                    if result_data.get("skipped"):
                        if device_id:
                            skipped_device_ids.append(str(device_id))

                if r.exception:
                    error_msg = str(r.exception)
                    if isinstance(r.exception, OTPRequiredException):
                        otp_required = r.exception

            if is_otp_timeout:
                results_dict[name] = {
                    "status": "otp_timeout",
                    "error": error_msg,
                    "result": None,
                }
            elif otp_required is not None:
                results_dict[name] = {
                    "status": "otp_required",
                    "error": error_msg,
                    "result": None,
                    "otp_dept_id": str(otp_required.dept_id),
                    "otp_device_group": otp_required.device_group,
                }
                if device_id:
                    otp_failed_device_ids.append(str(device_id))
                if otp_required_info is None:
                    otp_required_info = {
                        "otp_required": True,
                        "otp_dept_id": str(otp_required.dept_id),
                        "otp_device_group": otp_required.device_group,
                    }
            else:
                results_dict[name] = {
                    "status": "failed",
                    "error": error_msg,
                    "result": None,
                }
        else:
            r = multi_result[0]
            result_data = r.result or {}

            # 检查任务返回结果中的 success 标志
            task_success = result_data.get("success", True)  # 默认为 True（无异常即成功）
            if task_success:
                success_count += 1
                if device_id:
                    completed_device_ids.append(str(device_id))
            else:
                failed_count += 1

            results_dict[name] = {
                "status": "success" if task_success else "failed",
                "result": result_data.get("config"),
                "error": result_data.get("error") if not task_success else None,
            }

    # 构建汇总结果
    summary: dict[str, Any] = {
        "success": success_count,
        "failed": failed_count,
        "total": success_count + failed_count,
        "results": results_dict,
        "otp_failed_device_ids": otp_failed_device_ids,
        "completed_device_ids": completed_device_ids,
    }

    # 添加 OTP 超时信息（如果有）
    if otp_timeout_device_ids:
        summary["otp_timeout"] = True
        summary["otp_timeout_device_ids"] = otp_timeout_device_ids
        summary["skipped_device_ids"] = skipped_device_ids

    # 添加 OTP 认证信息（如果有）
    if otp_required_info:
        summary.update(otp_required_info)

    logger.info(
        "异步结果聚合完成",
        success=success_count,
        failed=failed_count,
        total=success_count + failed_count,
        otp_timeout_count=len(otp_timeout_device_ids),
    )

    return summary
