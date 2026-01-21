"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy.py
@DateTime: 2026-01-09 23:50:00
@Docs: 安全批量下发 Celery 任务。
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
from app.core.enums import AuthType, BackupStatus, BackupType, DeviceStatus, TaskStatus, TaskType
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.core.otp_service import otp_service
from app.crud.crud_credential import credential as credential_crud
from app.models.backup import Backup
from app.models.device import Device
from app.models.task import Task
from app.models.template import Template
from app.network.nornir_config import init_nornir
from app.network.nornir_tasks import aggregate_results, backup_config, deploy_from_host_data
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
    name="app.celery.tasks.deploy.deploy_task",
    queue="deploy",
    max_retries=0,  # 禁用自动重试，下发任务是高危操作
    autoretry_for=(),  # 不自动重试任何异常
)
def deploy_task(self, task_id: str) -> dict[str, Any]:
    """执行下发任务（灰度/并发/OTP断点续传）。"""
    celery_task_id = getattr(self.request, "id", None)
    logger.info("开始下发任务", task_id=celery_task_id, deploy_task_id=task_id)
    if celery_task_id:
        self.update_state(task_id=celery_task_id, state="PROGRESS", meta={"stage": "initializing"})

    try:
        return run_async(_deploy_task_async(self, task_id, celery_task_id=celery_task_id))
    except OTPRequiredException as otp_exc:
        # OTP 认证失败：标记为 PAUSED，让用户重新输入 OTP
        logger.info("下发需要 OTP 输入", deploy_task_id=task_id, message=otp_exc.message)
        try:
            run_async(_mark_task_paused(task_id, otp_exc.message, otp_exc.details))
        except Exception:
            pass
        return {"status": "paused", "otp_required": otp_exc.details}
    except Exception as e:
        error_text = str(e)
        logger.error("下发任务执行异常", deploy_task_id=task_id, error=error_text, exc_info=True)
        try:
            run_async(_mark_task_failed(task_id, error_text))
        except Exception:
            pass
        raise


async def _deploy_task_async(self, task_id: str, *, celery_task_id: str | None) -> dict[str, Any]:
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
        # 注意：Task 启用了 version_id 乐观锁；API 侧可能已写入 RUNNING/started_at。
        # 这里仅在必要时更新，并在并发冲突时回滚重试，避免 StaleDataError 直接让任务失败。
        task: Task | None = None
        for attempt in range(2):
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

            changed = False
            if task.status != TaskStatus.RUNNING.value:
                task.status = TaskStatus.RUNNING.value
                changed = True
            if task.started_at is None:
                task.started_at = datetime.now(UTC)
                changed = True

            if not changed:
                break

            try:
                await db.flush()
                await db.commit()
                break
            except StaleDataError:
                logger.warning("任务状态更新发生并发冲突，准备重试", deploy_task_id=task_id, attempt=attempt + 1)
                await db.rollback()
                if attempt >= 1:
                    raise
                continue

        if task is None:
            raise ValueError("任务不存在")

        template = await db.get(Template, task.template_id) if task.template_id else None
        if not template:
            raise ValueError("模板不存在")

        deploy_plan = task.deploy_plan or {}
        batch_size = int(deploy_plan.get("batch_size", 20))
        concurrency = int(deploy_plan.get("concurrency", 50))
        strict_allowlist = bool(deploy_plan.get("strict_allowlist", False))
        dry_run = bool(deploy_plan.get("dry_run", False))

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

        # 预渲染 + 校验（逐台）
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

        # 执行：按 batch 做灰度（每批并发执行）
        all_results: dict[str, Any] = {"results": {}}
        pre_change_backup_ids: dict[str, str] = {}
        for start in range(0, len(devices), batch_size):
            batch = devices[start : start + batch_size]
            _update_progress(
                {"stage": "executing", "batch_start": start, "batch_size": len(batch), "total": len(devices)}
            )

            hosts_data: list[dict[str, Any]] = []
            # OTP 可能在这里抛出，触发暂停（断点续传）
            try:
                for d in batch:
                    cred = await _get_device_credential(db, d, failed_devices=[str(x.id) for x in batch])
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

            # 变更前备份（best-effort）：使用独立 Nornir 实例，避免失败状态影响后续下发
            nr_backup = init_nornir(hosts_data, num_workers=min(concurrency, len(hosts_data)))
            backup_results = nr_backup.run(task=backup_config)
            backup_summary = aggregate_results(backup_results)
            for d in batch:
                host_key = str(d.id)
                r = backup_summary.get("results", {}).get(host_key, {})
                if r.get("status") == "success" and isinstance(r.get("result"), str):
                    b = await _save_pre_change_backup(db, d, r["result"])
                    pre_change_backup_ids[str(d.id)] = str(b.id)
                    if task.rollback_backup_id is None:
                        task.rollback_backup_id = b.id
            await db.commit()

            # 下发：使用新的 Nornir 实例，确保每台设备都会被选择执行
            nr_deploy = init_nornir(hosts_data, num_workers=min(concurrency, len(hosts_data)))
            deploy_results = nr_deploy.run(task=deploy_from_host_data)
            deploy_summary = aggregate_results(deploy_results)
            all_results["results"].update(deploy_summary.get("results", {}))

            # 兜底：若聚合结果里缺失某些 host，补记为失败，避免 success/failed 统计为 0
            for d in batch:
                host_key = str(d.id)
                if host_key not in all_results["results"]:
                    all_results["results"][host_key] = {
                        "status": "failed",
                        "error": "下发未执行或结果缺失",
                    }

        # 汇总
        success_count = 0
        failed_count = 0
        for _, r in all_results["results"].items():
            if r.get("status") == "success":
                success_count += 1
            else:
                failed_count += 1

        task.success_count = success_count
        task.failed_count = failed_count
        task.progress = 100
        task.status = TaskStatus.SUCCESS.value if failed_count == 0 else TaskStatus.PARTIAL.value
        task.result = {"render_hash": rendered_hash, "pre_change_backup_ids": pre_change_backup_ids, **all_results}
        task.finished_at = datetime.now(UTC)
        await db.flush()
        await db.commit()
        return {"status": task.status, "success": success_count, "failed": failed_count}


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.celery.tasks.deploy.rollback_task",
    queue="deploy",
)
def rollback_task(self, task_id: str) -> dict[str, Any]:
    """回滚下发任务（best-effort，先限定 H3C）。"""
    logger.info("开始回滚任务", task_id=self.request.id, deploy_task_id=task_id)
    return run_async(_rollback_task_async(self, task_id))


async def _rollback_task_async(self, task_id: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        task_uuid = UUID(task_id)
        task = await db.get(Task, task_uuid)
        if not task:
            raise ValueError("任务不存在")
        if task.task_type != TaskType.DEPLOY.value:
            raise ValueError("非下发任务")
        # 使用共享函数处理并发冲突
        await _update_task_status_with_retry(db, task, task_id)

        # 仅对 H3C/hp_comware 做 best-effort
        pre_change_backup_ids = {}
        if isinstance(task.result, dict):
            pre_change_backup_ids = task.result.get("pre_change_backup_ids", {}) or {}

        if not pre_change_backup_ids and not task.rollback_backup_id:
            return {"status": "failed", "error": "任务未记录变更前备份，无法回滚"}

        device_ids = (task.target_devices or {}).get("device_ids", []) if isinstance(task.target_devices, dict) else []
        devices = (await db.execute(select(Device).where(Device.id.in_([UUID(x) for x in device_ids])))).scalars().all()

        hosts_data: list[dict[str, Any]] = []
        verify_expected_md5: dict[str, str] = {}
        for d in devices:
            if d.vendor not in SUPPORTED_ROLLBACK_VENDORS:
                continue
            backup_id = pre_change_backup_ids.get(str(d.id))
            if not backup_id:
                continue
            backup = await db.get(Backup, UUID(backup_id))
            if not backup or not backup.content:
                continue
            cmds = normalize_rendered_config(backup.content)
            try:
                cred = await _get_device_credential(db, d, failed_devices=[str(d.id)])
            except OTPRequiredException as e:
                task.status = TaskStatus.PAUSED.value
                task.error_message = e.message
                task.result = e.details
                await db.flush()
                await db.commit()
                return {"status": "paused", "otp_required": e.details}
            verify_expected_md5[str(d.id)] = backup.md5_hash or ""
            hosts_data.append(
                {
                    "name": str(d.id),
                    "hostname": d.ip_address,
                    "platform": d.platform or get_platform_for_vendor(d.vendor),
                    "username": cred.username,
                    "password": cred.password,
                    "port": d.ssh_port or 22,
                    "data": {"deploy_configs": cmds, "device_id": str(d.id)},
                }
            )

        if not hosts_data:
            return {"status": "failed", "error": "无可回滚设备(支持 h3c/huawei/cisco)"}

        nr = init_nornir(hosts_data, num_workers=min(50, len(hosts_data)))
        results = nr.run(task=deploy_from_host_data)
        deploy_summary = aggregate_results(results)

        # 回滚验证：回滚后再次备份并比较 md5
        backup_results = nr.run(task=backup_config)
        backup_summary = aggregate_results(backup_results)
        verify: dict[str, Any] = {"matched": [], "mismatched": [], "missing": []}
        for host_id, expected_md5 in verify_expected_md5.items():
            r = backup_summary.get("results", {}).get(host_id, {})
            if r.get("status") != "success" or not isinstance(r.get("result"), str):
                verify["missing"].append(host_id)
                continue
            got_md5 = hashlib.md5(r["result"].encode("utf-8")).hexdigest()
            if expected_md5 and got_md5 == expected_md5:
                verify["matched"].append(host_id)
            else:
                verify["mismatched"].append({"device_id": host_id, "expected": expected_md5, "got": got_md5})

        task.status = TaskStatus.ROLLBACK.value
        task.result = {"deploy_summary": deploy_summary, "verify": verify}
        await db.flush()
        await db.commit()
        return {"status": "success", "deploy_summary": deploy_summary, "verify": verify}


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
    异步执行下发任务（使用 AsyncRunner + Scrapli Async）。

    与同步版本 deploy_task 相比：
    - 使用 AsyncRunner 替代 ThreadedRunner
    - 使用 asyncssh 替代 paramiko
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
    """异步下发任务的核心实现。"""
    from app.network.nornir_config import init_nornir
    from app.network.nornir_tasks import backup_config, deploy_from_host_data

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
        if not template:
            raise ValueError("模板不存在")

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

        nr = init_nornir(hosts_data, num_workers=concurrency)

        # 变更前备份（异步）- 使用 aggregate_results 检测 OTP 错误
        _update_progress({"stage": "pre_change_backup", "total": len(nr.inventory.hosts)})
        backup_results = nr.run(task=backup_config)
        backup_summary = aggregate_results(backup_results)

        # 检查是否有 OTP 错误
        if backup_summary.get("otp_required"):
            task.status = TaskStatus.PAUSED.value
            task.error_message = "需要重新输入 OTP 验证码"
            task.result = {
                "otp_required": True,
                "otp_dept_id": backup_summary.get("otp_dept_id"),
                "otp_device_group": backup_summary.get("otp_device_group"),
                "otp_failed_device_ids": backup_summary.get("otp_failed_device_ids", []),
            }
            await db.flush()
            await db.commit()
            return {"status": "paused", "otp_required": task.result}

        pre_change_backup_ids: dict[str, str] = {}
        for host_name, result_data in backup_summary.get("results", {}).items():
            if result_data.get("status") != "success":
                continue
            config_content = result_data.get("result")
            if config_content and isinstance(config_content, str):
                # 查找对应设备
                device = next((d for d in devices if str(d.id) == host_name), None)
                if device:
                    b = await _save_pre_change_backup(db, device, config_content)
                    pre_change_backup_ids[host_name] = str(b.id)
                    if task.rollback_backup_id is None:
                        task.rollback_backup_id = b.id
        await db.commit()

        # 异步下发 - 使用 aggregate_results 检测 OTP 错误
        _update_progress({"stage": "deploying", "total": len(nr.inventory.hosts)})
        deploy_results = nr.run(task=deploy_from_host_data)
        deploy_summary = aggregate_results(deploy_results)

        # 检查下发是否有 OTP 错误
        if deploy_summary.get("otp_required"):
            task.status = TaskStatus.PAUSED.value
            task.error_message = "需要重新输入 OTP 验证码"
            task.result = {
                "otp_required": True,
                "otp_dept_id": deploy_summary.get("otp_dept_id"),
                "otp_device_group": deploy_summary.get("otp_device_group"),
                "otp_failed_device_ids": deploy_summary.get("otp_failed_device_ids", []),
                "pre_change_backup_ids": pre_change_backup_ids,
            }
            await db.flush()
            await db.commit()
            return {"status": "paused", "otp_required": task.result}

        # 聚合结果 - 直接使用 aggregate_results 返回的格式化数据
        all_results: dict[str, Any] = {"results": deploy_summary.get("results", {})}
        success_count = deploy_summary.get("success", 0)
        failed_count = deploy_summary.get("failed", 0)

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
