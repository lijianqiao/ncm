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
    logger.info("开始下发任务", task_id=self.request.id, deploy_task_id=task_id)
    self.update_state(state="PROGRESS", meta={"stage": "initializing"})

    return run_async(_deploy_task_async(self, task_id))


async def _deploy_task_async(self, task_id: str) -> dict[str, Any]:
    render_service = RenderService()

    async with AsyncSessionLocal() as db:
        task_uuid = UUID(task_id)
        task = await db.get(Task, task_uuid)
        if not task:
            raise ValueError("任务不存在")
        if task.task_type != TaskType.DEPLOY.value:
            raise ValueError("非下发任务")

        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(UTC)
        await db.flush()
        await db.commit()

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
            self.update_state(state="PROGRESS", meta={"stage": "rendering", "progress": idx, "total": len(devices)})
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
            self.update_state(
                state="PROGRESS",
                meta={"stage": "executing", "batch_start": start, "batch_size": len(batch), "total": len(devices)},
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
                            "data": {"deploy_configs": rendered_map[str(d.id)], "device_id": str(d.id)},
                        }
                    )
            except OTPRequiredException as e:
                task.status = TaskStatus.PAUSED.value
                task.error_message = e.message
                task.result = e.details
                await db.flush()
                await db.commit()
                return {"status": "paused", "otp_required": e.details}

            nr = init_nornir(hosts_data, num_workers=min(concurrency, len(hosts_data)))

            # 变更前备份（best-effort）：在同一批次内先备份再下发
            backup_results = nr.run(task=backup_config)
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

            # 下发
            deploy_results = nr.run(task=deploy_from_host_data)
            deploy_summary = aggregate_results(deploy_results)
            all_results["results"].update(deploy_summary.get("results", {}))

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
        task.status = TaskStatus.RUNNING.value
        await db.flush()
        await db.commit()

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
            if d.vendor != "h3c":
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
                    "platform": d.platform or "hp_comware",
                    "username": cred.username,
                    "password": cred.password,
                    "port": d.ssh_port or 22,
                    "data": {"deploy_configs": cmds, "device_id": str(d.id)},
                }
            )

        if not hosts_data:
            return {"status": "failed", "error": "无可回滚设备(仅支持 h3c)"}

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
