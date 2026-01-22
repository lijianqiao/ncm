"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy.py
@DateTime: 2026-01-09 23:50:00
@Docs: 安全批量下发 Celery 任务（纯异步实现）。

使用 AsyncRunner + AsyncScrapli (asyncssh) 实现高效网络自动化。
"""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async
from app.core.command_policy import normalize_rendered_config, validate_commands
from app.core.db import AsyncSessionLocal
from app.core.enums import (
    ApprovalStatus,
    AuthType,
    BackupStatus,
    BackupType,
    DeviceStatus,
    TaskStatus,
    TaskType,
    TemplateStatus,
)
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.core.otp_service import otp_service
from app.crud.crud_credential import credential as credential_crud
from app.models.backup import Backup
from app.models.device import Device
from app.models.task import Task
from app.models.template import Template
from app.network.platform_config import get_platform_for_vendor
from app.services.render_service import RenderService

# 支持回滚的厂商列表（扩展支持 Huawei/Cisco）
SUPPORTED_ROLLBACK_VENDORS: set[str] = {"h3c", "huawei", "cisco"}


async def _mark_task_paused(task_id: str, message: str, details: dict[str, Any] | None = None) -> None:
    """将任务标记为暂停状态（OTP 认证失败时使用）。"""
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, UUID(task_id))
        if not task:
            return
        task.status = TaskStatus.PAUSED.value
        task.error_message = message
        task.result = details
        await db.flush()
        await db.commit()


async def _mark_task_failed(task_id: str, error_message: str) -> None:
    """将任务标记为失败状态。"""
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, UUID(task_id))
        if not task:
            return
        task.status = TaskStatus.FAILED.value
        task.error_message = error_message
        task.finished_at = datetime.now(UTC)
        await db.flush()
        await db.commit()


async def _update_task_status_with_retry(
    db,
    task: Task,
    task_id: str,
    *,
    set_running: bool = True,
    set_started_at: bool = True,
    max_attempts: int = 2,
) -> None:
    """
    带并发冲突重试的任务状态更新。

    处理 Task 表启用 version_id 乐观锁时的 StaleDataError。

    Args:
        db: 数据库 Session
        task: 任务对象
        task_id: 任务 ID（仅用于日志）
        set_running: 是否设置状态为 RUNNING
        set_started_at: 是否设置 started_at
        max_attempts: 最大重试次数
    """
    for attempt in range(max_attempts):
        changed = False
        if set_running and task.status != TaskStatus.RUNNING.value:
            task.status = TaskStatus.RUNNING.value
            changed = True
        if set_started_at and task.started_at is None:
            task.started_at = datetime.now(UTC)
            changed = True

        if not changed:
            return

        try:
            await db.flush()
            await db.commit()
            return
        except StaleDataError:
            logger.warning(
                "任务状态更新发生并发冲突，准备重试",
                deploy_task_id=task_id,
                attempt=attempt + 1,
            )
            await db.rollback()
            # 重新获取任务对象
            await db.refresh(task)
            if attempt >= max_attempts - 1:
                raise


def _check_otp_exception_in_results(results) -> OTPRequiredException | None:
    """检查异步任务结果中是否包含 OTP 认证异常。

    Args:
        results: AsyncRunner 返回的 AggregatedResult

    Returns:
        OTPRequiredException | None: 如果存在 OTP 异常则返回，否则返回 None
    """
    for _host_name, multi_result in results.items():
        if multi_result.failed:
            exc = multi_result[0].exception if multi_result else None
            if isinstance(exc, OTPRequiredException):
                return exc
    return None


async def _get_device_credential(db, device: Device, failed_devices: list[str] | None = None):
    auth_type = AuthType(device.auth_type)

    if auth_type == AuthType.STATIC:
        if not device.username or not device.password_encrypted:
            raise ValueError("设备缺少用户名或密码配置")
        return await otp_service.get_credential_for_static_device(device.username, device.password_encrypted)

    if not device.dept_id:
        raise ValueError("设备缺少部门关联")

    credential = await credential_crud.get_by_dept_and_group(db, device.dept_id, device.device_group)
    if not credential:
        raise ValueError("设备组凭据未配置")

    if auth_type == AuthType.OTP_SEED:
        if not credential.otp_seed_encrypted:
            raise ValueError("设备组 OTP 种子未配置")
        return await otp_service.get_credential_for_otp_seed_device(credential.username, credential.otp_seed_encrypted)

    if auth_type == AuthType.OTP_MANUAL:
        return await otp_service.get_credential_for_otp_manual_device(
            username=credential.username,
            dept_id=device.dept_id,
            device_group=device.device_group,
            failed_devices=failed_devices,
        )

    raise ValueError(f"不支持的认证类型: {auth_type}")


async def _save_pre_change_backup(db, device: Device, config_content: str) -> Backup:
    content_size = len(config_content.encode("utf-8"))
    md5_hash = hashlib.md5(config_content.encode("utf-8")).hexdigest()
    backup = Backup(
        device_id=device.id,
        backup_type=BackupType.PRE_CHANGE.value,
        status=BackupStatus.SUCCESS.value,
        content=config_content,
        content_size=content_size,
        md5_hash=md5_hash,
        operator_id=None,
    )
    db.add(backup)
    await db.flush()
    await db.refresh(backup)
    return backup


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.deploy.rollback_task",
    queue="deploy",
    max_retries=0,
    autoretry_for=(),
)
def rollback_task(self, task_id: str) -> dict[str, Any]:
    """回滚下发任务（best-effort，先限定 H3C）。

    若遇到 OTP 认证失败，会将任务状态置为 PAUSED 并返回 otp_required 信息。
    """
    logger.info("开始回滚任务", task_id=self.request.id, deploy_task_id=task_id)
    try:
        return run_async(_rollback_task_async(self, task_id))
    except OTPRequiredException as otp_exc:
        # OTP 认证失败：标记为 PAUSED，让用户重新输入 OTP
        logger.info("回滚需要 OTP 输入", deploy_task_id=task_id, message=otp_exc.message)
        try:
            run_async(_mark_task_paused(task_id, otp_exc.message, otp_exc.details))
        except Exception:
            pass
        return {"status": "paused", "otp_required": otp_exc.details}
    except Exception as e:
        error_text = str(e)
        logger.error("回滚任务执行异常", deploy_task_id=task_id, error=error_text, exc_info=True)
        try:
            run_async(_mark_task_failed(task_id, error_text))
        except Exception:
            pass
        raise


async def _rollback_task_async(self, task_id: str) -> dict[str, Any]:
    """回滚任务的核心实现（纯异步）。"""
    from app.network.async_runner import run_async_tasks
    from app.network.async_tasks import async_collect_config, async_deploy_from_host_data
    from app.network.nornir_config import init_nornir_async

    async with AsyncSessionLocal() as db:
        task_uuid = UUID(task_id)
        task = await db.get(Task, task_uuid)
        if not task:
            raise ValueError("任务不存在")
        if task.task_type != TaskType.DEPLOY.value:
            raise ValueError("非下发任务")

        # 状态检查：只允许 SUCCESS、PARTIAL 或 ROLLBACK 状态回滚
        allowed_statuses = {TaskStatus.SUCCESS.value, TaskStatus.PARTIAL.value, TaskStatus.ROLLBACK.value}
        if task.status not in allowed_statuses:
            return {
                "status": "failed",
                "error": f"任务状态为 {task.status}，无法回滚（仅成功、部分成功或已回滚的任务可回滚）",
            }

        # 使用共享函数处理并发冲突
        await _update_task_status_with_retry(db, task, task_id)

        # 获取变更前备份信息
        pre_change_backup_ids = {}
        if isinstance(task.result, dict):
            pre_change_backup_ids = task.result.get("pre_change_backup_ids", {}) or {}

        if not pre_change_backup_ids and not task.rollback_backup_id:
            return {"status": "failed", "error": "任务未记录变更前备份，无法回滚"}

        device_ids = (task.target_devices or {}).get("device_ids", []) if isinstance(task.target_devices, dict) else []
        devices = (await db.execute(select(Device).where(Device.id.in_([UUID(x) for x in device_ids])))).scalars().all()

        # 第一步：收集设备信息，检测哪些设备可以回滚
        check_hosts_data: list[dict[str, Any]] = []
        backup_info: dict[str, dict[str, Any]] = {}  # device_id -> {backup, expected_md5, cmds}
        skipped_devices: list[dict[str, Any]] = []
        cannot_rollback_devices: list[dict[str, Any]] = []

        for d in devices:
            device_id_str = str(d.id)

            # 检查厂商支持
            if d.vendor and d.vendor.lower() not in SUPPORTED_ROLLBACK_VENDORS:
                cannot_rollback_devices.append({
                    "device_id": device_id_str,
                    "device_name": d.name,
                    "reason": f"厂商 {d.vendor} 暂不支持回滚",
                })
                continue

            # 检查备份存在
            backup_id = pre_change_backup_ids.get(device_id_str)
            if not backup_id:
                cannot_rollback_devices.append({
                    "device_id": device_id_str,
                    "device_name": d.name,
                    "reason": "无变更前备份",
                })
                continue

            backup = await db.get(Backup, UUID(backup_id))
            if not backup or not backup.content:
                cannot_rollback_devices.append({
                    "device_id": device_id_str,
                    "device_name": d.name,
                    "reason": "变更前备份内容不存在",
                })
                continue

            # 获取凭据
            try:
                cred = await _get_device_credential(db, d, failed_devices=[device_id_str])
            except OTPRequiredException as e:
                task.status = TaskStatus.PAUSED.value
                task.error_message = e.message
                task.result = e.details
                await db.flush()
                await db.commit()
                return {"status": "paused", "otp_required": e.details}
            except Exception as e:
                cannot_rollback_devices.append({
                    "device_id": device_id_str,
                    "device_name": d.name,
                    "reason": f"凭据获取失败: {e}",
                })
                continue

            expected_md5 = backup.md5_hash or hashlib.md5(backup.content.encode("utf-8")).hexdigest()
            cmds = normalize_rendered_config(backup.content)

            backup_info[device_id_str] = {
                "backup": backup,
                "expected_md5": expected_md5,
                "cmds": cmds,
                "device": d,
                "cred": cred,
            }

            check_hosts_data.append({
                "name": device_id_str,
                "hostname": d.ip_address,
                "platform": d.platform or get_platform_for_vendor(d.vendor),
                "username": cred.username,
                "password": cred.password,
                "port": d.ssh_port or 22,
                "data": {
                    "device_id": device_id_str,
                    "auth_type": d.auth_type,
                    "dept_id": str(d.dept_id) if d.dept_id else None,
                    "device_group": d.device_group,
                },
            })

        if not check_hosts_data:
            return {
                "status": "failed",
                "error": "无可回滚设备",
                "cannot_rollback": cannot_rollback_devices,
            }

        # 第二步：获取当前配置，比对 MD5（异步）
        check_inventory = init_nornir_async(check_hosts_data)
        current_backup_results = await run_async_tasks(
            check_inventory.hosts,
            async_collect_config,
            num_workers=min(50, len(check_hosts_data)),
        )

        # 检查是否有 OTP 异常（设备连接时发现 OTP 过期/失效）
        otp_exc = _check_otp_exception_in_results(current_backup_results)
        if otp_exc:
            raise otp_exc

        # 分类：需要回滚 vs 跳过（配置未变化）
        rollback_hosts_data: list[dict[str, Any]] = []
        verify_expected_md5: dict[str, str] = {}

        for device_id_str, info in backup_info.items():
            expected_md5 = info["expected_md5"]
            device = info["device"]

            # 获取异步结果
            multi_result = current_backup_results.get(device_id_str)
            result_data = None
            if multi_result and not multi_result.failed:
                result_data = multi_result[0].result if multi_result else None

            if not result_data or not result_data.get("success"):
                # 无法获取当前配置，尝试回滚
                logger.warning("无法获取当前配置，仍尝试回滚", device_id=device_id_str)
            else:
                current_config = result_data.get("config", "")
                current_md5 = hashlib.md5(current_config.encode("utf-8")).hexdigest() if current_config else ""

                if current_md5 == expected_md5:
                    # 配置未变化，跳过
                    skipped_devices.append({
                        "device_id": device_id_str,
                        "device_name": device.name,
                        "reason": "配置未变化",
                        "current_md5": current_md5,
                        "expected_md5": expected_md5,
                    })
                    logger.info("配置未变化，跳过回滚", device_id=device_id_str)
                    continue

            # 需要回滚
            cred = info["cred"]
            cmds = info["cmds"]
            verify_expected_md5[device_id_str] = expected_md5
            rollback_hosts_data.append({
                "name": device_id_str,
                "hostname": device.ip_address,
                "platform": device.platform or get_platform_for_vendor(device.vendor),
                "username": cred.username,
                "password": cred.password,
                "port": device.ssh_port or 22,
                "data": {
                    "deploy_configs": cmds,
                    "device_id": device_id_str,
                    "auth_type": device.auth_type,
                    "dept_id": str(device.dept_id) if device.dept_id else None,
                    "device_group": device.device_group,
                },
            })

        if not rollback_hosts_data:
            # 所有设备都跳过了
            task.status = TaskStatus.ROLLBACK.value
            task.result = {
                "skipped": skipped_devices,
                "cannot_rollback": cannot_rollback_devices,
                "message": "所有设备配置未变化，无需回滚",
            }
            await db.flush()
            await db.commit()
            return {
                "status": "success",
                "message": "所有设备配置未变化，无需回滚",
                "skipped": skipped_devices,
                "cannot_rollback": cannot_rollback_devices,
            }

        # 第三步：执行回滚（异步）
        rollback_inventory = init_nornir_async(rollback_hosts_data)
        deploy_results = await run_async_tasks(
            rollback_inventory.hosts,
            async_deploy_from_host_data,
            num_workers=min(50, len(rollback_hosts_data)),
        )

        # 检查是否有 OTP 异常
        otp_exc = _check_otp_exception_in_results(deploy_results)
        if otp_exc:
            raise otp_exc

        # 处理回滚结果
        deploy_summary: dict[str, Any] = {"results": {}, "success": 0, "failed": 0}
        for host_name, multi_result in deploy_results.items():
            if multi_result.failed:
                deploy_summary["results"][host_name] = {
                    "status": "failed",
                    "error": str(multi_result[0].exception) if multi_result else "Unknown error",
                }
                deploy_summary["failed"] += 1
            else:
                result_data = multi_result[0].result if multi_result else None
                if result_data and result_data.get("success"):
                    deploy_summary["results"][host_name] = {
                        "status": "success",
                        "result": result_data.get("result"),
                    }
                    deploy_summary["success"] += 1
                else:
                    deploy_summary["results"][host_name] = {
                        "status": "failed",
                        "error": result_data.get("error") if result_data else "Unknown error",
                    }
                    deploy_summary["failed"] += 1

        # 第四步：回滚验证 - 再次备份并比较 MD5（异步）
        verify_results = await run_async_tasks(
            rollback_inventory.hosts,
            async_collect_config,
            num_workers=min(50, len(rollback_hosts_data)),
        )

        # 检查是否有 OTP 异常（验证阶段）
        otp_exc = _check_otp_exception_in_results(verify_results)
        if otp_exc:
            # 验证阶段 OTP 失败不直接抛出，记录警告继续处理
            logger.warning("回滚验证阶段 OTP 异常，跳过验证", error=otp_exc.message)

        verify: dict[str, Any] = {"matched": [], "mismatched": [], "missing": []}
        for host_id, expected_md5 in verify_expected_md5.items():
            multi_result = verify_results.get(host_id)
            result_data = None
            if multi_result and not multi_result.failed:
                result_data = multi_result[0].result if multi_result else None

            if not result_data or not result_data.get("success"):
                verify["missing"].append(host_id)
                continue

            current_config = result_data.get("config", "")
            got_md5 = hashlib.md5(current_config.encode("utf-8")).hexdigest() if current_config else ""

            if expected_md5 and got_md5 == expected_md5:
                verify["matched"].append(host_id)
            else:
                verify["mismatched"].append({"device_id": host_id, "expected": expected_md5, "got": got_md5})

        task.status = TaskStatus.ROLLBACK.value
        task.result = {
            "deploy_summary": deploy_summary,
            "verify": verify,
            "skipped": skipped_devices,
            "cannot_rollback": cannot_rollback_devices,
            "rolled_back_count": len(rollback_hosts_data),
            "skipped_count": len(skipped_devices),
        }
        task.finished_at = datetime.now(UTC)
        await db.flush()
        await db.commit()

        logger.info(
            "回滚任务完成",
            task_id=task_id,
            rolled_back=len(rollback_hosts_data),
            skipped=len(skipped_devices),
            cannot_rollback=len(cannot_rollback_devices),
        )

        return {
            "status": "success",
            "deploy_summary": deploy_summary,
            "verify": verify,
            "skipped": skipped_devices,
            "cannot_rollback": cannot_rollback_devices,
        }


# ===== 异步版本下发任务 (Phase 3 - AsyncRunner) =====


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.deploy.async_deploy_task",
    queue="deploy",
    max_retries=0,
    autoretry_for=(),
)
def async_deploy_task(self, task_id: str) -> dict[str, Any]:
    """
    执行下发任务（使用 AsyncRunner + Scrapli Async）。

    特性：
    - 使用 AsyncRunner 实现真正的异步并发
    - 使用 asyncssh 作为底层 SSH 传输
    - 显著降低资源开销，支持更高并发

    Args:
        task_id: 任务 ID（Task 表主键）

    Returns:
        dict: 下发结果
    """
    celery_task_id = getattr(self.request, "id", None)
    logger.info("开始异步下发任务", task_id=celery_task_id, deploy_task_id=task_id)
    if celery_task_id:
        self.update_state(task_id=celery_task_id, state="PROGRESS", meta={"stage": "initializing"})

    try:
        return run_async(_async_deploy_task_impl(self, task_id, celery_task_id=celery_task_id))
    except OTPRequiredException as otp_exc:
        # OTP 认证失败：标记为 PAUSED，让用户重新输入 OTP
        logger.info("异步下发需要 OTP 输入", deploy_task_id=task_id, message=otp_exc.message)
        try:
            run_async(_mark_task_paused(task_id, otp_exc.message, otp_exc.details))
        except Exception:
            pass
        # 返回 paused 状态而不是抛出异常
        return {"status": "paused", "otp_required": otp_exc.details}
    except Exception as e:
        error_text = str(e)
        logger.error("异步下发任务执行异常", deploy_task_id=task_id, error=error_text, exc_info=True)
        try:
            run_async(_mark_task_failed(task_id, error_text))
        except Exception:
            pass
        raise


async def _async_deploy_task_impl(self, task_id: str, *, celery_task_id: str | None) -> dict[str, Any]:
    """异步下发任务的核心实现（纯异步）。"""
    from app.network.async_runner import run_async_tasks
    from app.network.async_tasks import async_collect_config, async_deploy_from_host_data
    from app.network.nornir_config import init_nornir_async

    render_service = RenderService()

    def _update_progress(meta: dict[str, Any]) -> None:
        if not celery_task_id:
            return
        try:
            self.update_state(task_id=celery_task_id, state="PROGRESS", meta=meta)
        except Exception:
            return

    async with AsyncSessionLocal() as db:
        task_uuid = UUID(task_id)
        task = await db.get(Task, task_uuid)
        if not task:
            raise ValueError("任务不存在")
        if task.task_type != TaskType.DEPLOY.value:
            raise ValueError("非下发任务")

        # 检查任务状态：如果已暂停/取消/失败，则不继续执行
        if task.status in {
            TaskStatus.PAUSED.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.FAILED.value,
            TaskStatus.SUCCESS.value,
            TaskStatus.PARTIAL.value,
        }:
            logger.info(
                "任务状态不允许执行，跳过",
                deploy_task_id=task_id,
                current_status=task.status,
            )
            return {"status": task.status, "skipped": True, "reason": f"任务状态为 {task.status}"}

        # 使用共享函数处理并发冲突
        await _update_task_status_with_retry(db, task, task_id)

        template = await db.get(Template, task.template_id) if task.template_id else None
        if not template or template.is_deleted:
            raise ValueError("模板不存在或已被删除")
        if template.status != TemplateStatus.APPROVED.value or template.approval_status != ApprovalStatus.APPROVED.value:
            raise ValueError("模板未处于已审批状态")

        deploy_plan = task.deploy_plan or {}
        concurrency = int(deploy_plan.get("concurrency", 100))
        strict_allowlist = bool(deploy_plan.get("strict_allowlist", False))
        dry_run = bool(deploy_plan.get("dry_run", False))

        # 获取目标设备
        device_ids = []
        if task.target_devices and isinstance(task.target_devices, dict):
            device_ids = task.target_devices.get("device_ids", []) or []
        devices = (await db.execute(select(Device).where(Device.id.in_([UUID(x) for x in device_ids])))).scalars().all()
        devices = [d for d in devices if d.status == DeviceStatus.ACTIVE.value]

        if not devices:
            task.status = TaskStatus.FAILED.value
            task.error_message = "没有可下发的设备"
            await db.flush()
            await db.commit()
            return {"status": "failed", "error": task.error_message}

        # 预渲染 + 校验
        _update_progress({"stage": "rendering", "total": len(devices)})
        rendered_map: dict[str, list[str]] = {}
        rendered_hash: dict[str, str] = {}
        failed_devices: list[str] = []

        for idx, device in enumerate(devices, start=1):
            _update_progress({"stage": "rendering", "progress": idx, "total": len(devices)})
            try:
                rendered = render_service.render(template, task.template_params or {}, device=device)
                cmds = normalize_rendered_config(rendered)
                validate_commands(cmds, strict_allowlist=strict_allowlist)
                rendered_map[str(device.id)] = cmds
                rendered_hash[str(device.id)] = hashlib.md5(rendered.encode("utf-8")).hexdigest()
            except Exception as e:
                failed_devices.append(str(device.id))
                logger.warning("渲染/校验失败", device_id=str(device.id), error=str(e))

        if failed_devices:
            task.failed_count = len(failed_devices)
            task.success_count = 0
            task.status = TaskStatus.FAILED.value
            task.result = {"failed_devices": failed_devices, "stage": "render"}
            task.error_message = "部分设备渲染/校验失败"
            await db.flush()
            await db.commit()
            return {"status": "failed", "failed_devices": failed_devices}

        if dry_run:
            task.status = TaskStatus.SUCCESS.value
            task.progress = 100
            task.success_count = len(rendered_map)
            task.failed_count = 0
            task.result = {"render_hash": rendered_hash, "dry_run": True}
            task.finished_at = datetime.now(UTC)
            await db.flush()
            await db.commit()
            return {"status": "success", "dry_run": True, "devices": len(rendered_map)}

        # 构建异步 hosts_data
        _update_progress({"stage": "preparing_credentials", "total": len(devices)})
        hosts_data: list[dict[str, Any]] = []
        for d in devices:
            try:
                cred = await _get_device_credential(db, d, failed_devices=[str(x.id) for x in devices])
                platform = d.platform or get_platform_for_vendor(d.vendor)
                hosts_data.append(
                    {
                        "name": str(d.id),
                        "hostname": d.ip_address,
                        "platform": platform,
                        "username": cred.username,
                        "password": cred.password,
                        "port": d.ssh_port or 22,
                        "groups": [d.device_group] if d.device_group else [],
                        "data": {
                            "deploy_configs": rendered_map[str(d.id)],
                            "device_id": str(d.id),
                            "device_name": d.name,
                            # OTP 认证所需字段
                            "auth_type": d.auth_type,
                            "dept_id": str(d.dept_id) if d.dept_id else None,
                            "device_group": d.device_group,
                        },
                    }
                )
            except OTPRequiredException as e:
                task.status = TaskStatus.PAUSED.value
                task.error_message = e.message
                task.result = e.details
                await db.flush()
                await db.commit()
                return {"status": "paused", "otp_required": e.details}
            except Exception as e:
                logger.warning("获取凭据失败", device_id=str(d.id), error=str(e))
                failed_devices.append(str(d.id))

        if not hosts_data:
            task.status = TaskStatus.FAILED.value
            task.error_message = "所有设备凭据获取失败"
            await db.flush()
            await db.commit()
            return {"status": "failed", "error": task.error_message}

        # 初始化异步 Inventory
        inventory = init_nornir_async(hosts_data)
        total_hosts = len(inventory.hosts)

        # 变更前备份（异步）
        _update_progress({"stage": "pre_change_backup", "total": total_hosts})

        backup_results = await run_async_tasks(
            inventory.hosts,
            async_collect_config,
            num_workers=concurrency,
        )

        # 处理备份结果
        pre_change_backup_ids: dict[str, str] = {}
        backup_otp_errors: list[str] = []

        for host_name, multi_result in backup_results.items():
            if multi_result.failed:
                exc = multi_result[0].exception if multi_result else None
                if isinstance(exc, OTPRequiredException):
                    backup_otp_errors.append(host_name)
                continue

            result_data = multi_result[0].result if multi_result else None
            if not result_data or not result_data.get("success"):
                continue

            config_content = result_data.get("config")
            if config_content and isinstance(config_content, str):
                device = next((d for d in devices if str(d.id) == host_name), None)
                if device:
                    b = await _save_pre_change_backup(db, device, config_content)
                    pre_change_backup_ids[host_name] = str(b.id)
                    if task.rollback_backup_id is None:
                        task.rollback_backup_id = b.id

        # 检查是否有 OTP 错误
        if backup_otp_errors:
            task.status = TaskStatus.PAUSED.value
            task.error_message = "需要重新输入 OTP 验证码"
            task.result = {
                "otp_required": True,
                "otp_failed_device_ids": backup_otp_errors,
            }
            await db.flush()
            await db.commit()
            return {"status": "paused", "otp_required": task.result}

        await db.commit()

        # 异步下发
        _update_progress({"stage": "deploying", "total": total_hosts})

        deploy_results = await run_async_tasks(
            inventory.hosts,
            async_deploy_from_host_data,
            num_workers=concurrency,
        )

        # 处理下发结果
        deploy_otp_errors: list[str] = []
        all_results: dict[str, Any] = {"results": {}}
        success_count = 0
        failed_count = 0

        for host_name, multi_result in deploy_results.items():
            if multi_result.failed:
                exc = multi_result[0].exception if multi_result else None
                if isinstance(exc, OTPRequiredException):
                    deploy_otp_errors.append(host_name)
                all_results["results"][host_name] = {
                    "status": "failed",
                    "error": str(exc) if exc else "Unknown error",
                }
                failed_count += 1
                continue

            result_data = multi_result[0].result if multi_result else None
            if result_data and result_data.get("success"):
                all_results["results"][host_name] = {
                    "status": "success",
                    "result": result_data.get("result"),
                }
                success_count += 1
            else:
                all_results["results"][host_name] = {
                    "status": "failed",
                    "error": result_data.get("error") if result_data else "Unknown error",
                }
                failed_count += 1

        # 检查下发是否有 OTP 错误
        if deploy_otp_errors:
            task.status = TaskStatus.PAUSED.value
            task.error_message = "需要重新输入 OTP 验证码"
            task.result = {
                "otp_required": True,
                "otp_failed_device_ids": deploy_otp_errors,
                "pre_change_backup_ids": pre_change_backup_ids,
            }
            await db.flush()
            await db.commit()
            return {"status": "paused", "otp_required": task.result}

        # 更新任务状态
        task.success_count = success_count
        task.failed_count = failed_count
        task.progress = 100
        task.status = TaskStatus.SUCCESS.value if failed_count == 0 else TaskStatus.PARTIAL.value
        task.result = {
            "render_hash": rendered_hash,
            "pre_change_backup_ids": pre_change_backup_ids,
            **all_results,
        }
        task.finished_at = datetime.now(UTC)
        await db.flush()
        await db.commit()

        logger.info(
            "异步下发任务完成",
            task_id=task_id,
            success=success_count,
            failed=failed_count,
        )

        return {"status": task.status, "success": success_count, "failed": failed_count}
