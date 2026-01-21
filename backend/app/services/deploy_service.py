"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy_service.py
@DateTime: 2026-01-09 23:40:00
@Docs: 安全批量下发服务（任务创建/审批/执行/回滚入口）。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import ApprovalStatus, AuthType, DeviceStatus, TaskStatus, TaskType
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.otp_service import otp_service
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.crud.crud_task import CRUDTask
from app.crud.crud_task_approval import CRUDTaskApprovalStep
from app.models.task import Task
from app.models.task_approval import TaskApprovalStep
from app.schemas.deploy import DeployCreateRequest, DeviceDeployResult


class DeployService:
    def __init__(
        self,
        db: AsyncSession,
        task_crud: CRUDTask,
        task_approval_crud: CRUDTaskApprovalStep,
        device_crud: CRUDDevice,
        credential_crud: CRUDCredential,
    ):
        self.db = db
        self.task_crud = task_crud
        self.task_approval_crud = task_approval_crud
        self.device_crud = device_crud
        self.credential_crud = credential_crud

    def _get_target_device_ids(self, task: Task) -> list[UUID]:
        if not task.target_devices or not isinstance(task.target_devices, dict):
            return []
        raw_ids = task.target_devices.get("device_ids", []) or []
        device_ids: list[UUID] = []
        for x in raw_ids:
            try:
                device_ids.append(UUID(str(x)))
            except Exception:
                continue
        return device_ids

    async def get_task(self, task_id: UUID) -> Task:
        task = await self.task_crud.get_with_related(self.db, id=task_id)
        if not task:
            raise NotFoundException("任务不存在")
        if task.task_type != TaskType.DEPLOY.value:
            raise NotFoundException("任务类型不匹配")
        return task

    async def list_tasks_paginated(self, *, page: int = 1, page_size: int = 20) -> tuple[list[Task], int]:
        return await self.task_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            task_type=TaskType.DEPLOY.value,
            with_related=True,
        )

    async def list_deleted_tasks_paginated(self, *, page: int = 1, page_size: int = 20) -> tuple[list[Task], int]:
        return await self.task_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            task_type=TaskType.DEPLOY.value,
            with_related=True,
        )

    async def _get_deploy_task_ids(self, *, ids: list[UUID]) -> list[UUID]:
        if not ids:
            return []
        stmt = select(Task.id).where(Task.id.in_(ids), Task.task_type == TaskType.DEPLOY.value)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @transactional()
    async def batch_delete_tasks(self, *, ids: list[UUID], hard_delete: bool = False) -> tuple[int, list[UUID]]:
        allowed_ids = await self._get_deploy_task_ids(ids=ids)
        allowed_set = set(allowed_ids)
        success_count, failed_ids = await self.task_crud.batch_remove(self.db, ids=allowed_ids, hard_delete=hard_delete)
        for id_ in ids:
            if id_ not in allowed_set and id_ not in failed_ids:
                failed_ids.append(id_)
        return success_count, failed_ids

    @transactional()
    async def delete_task(self, *, task_id: UUID) -> Task:
        task = await self.get_task(task_id)
        success_count, failed_ids = await self.batch_delete_tasks(ids=[task_id], hard_delete=False)
        if success_count == 0 or failed_ids:
            raise NotFoundException("删除失败")
        return task

    @transactional()
    async def batch_restore_tasks(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        allowed_ids = await self._get_deploy_task_ids(ids=ids)
        allowed_set = set(allowed_ids)
        success_count, failed_ids = await self.task_crud.batch_restore(self.db, ids=allowed_ids)
        for id_ in ids:
            if id_ not in allowed_set and id_ not in failed_ids:
                failed_ids.append(id_)
        return success_count, failed_ids

    @transactional()
    async def restore_task(self, *, task_id: UUID) -> Task:
        success_count, failed_ids = await self.batch_restore_tasks(ids=[task_id])
        if success_count == 0 or failed_ids:
            raise NotFoundException("任务不存在或未被删除")
        return await self.get_task(task_id)

    @transactional()
    async def hard_delete_task(self, *, task_id: UUID) -> None:
        stmt = select(Task.id).where(
            Task.id == task_id, Task.task_type == TaskType.DEPLOY.value, Task.is_deleted.is_(True)
        )
        exists = (await self.db.execute(stmt)).scalars().first()
        if exists is None:
            raise NotFoundException("任务不存在或未被软删除")
        success_count, failed_ids = await self.batch_delete_tasks(ids=[task_id], hard_delete=True)
        if success_count == 0 or failed_ids:
            raise NotFoundException("彻底删除失败")

    async def get_device_results(self, task: Task) -> list[DeviceDeployResult]:
        """获取设备维度的执行结果列表（补充设备名称）。"""
        device_ids = self._get_target_device_ids(task)
        if not device_ids:
            return []

        # 批量查询设备信息
        devices = await self.device_crud.get_multi_by_ids(self.db, ids=device_ids)
        device_map = {d.id: d for d in devices}

        # 解析任务执行结果
        # task.result 结构可能是:
        # 1. 正常执行: {"results": { "uuid": {"status": "success", "result": "...", "error": null} }}
        # 2. 暂停/OTP: {"otp_required": true, ...}
        # 3. 未开始: None or {}
        task_results = {}
        if task.result and isinstance(task.result, dict):
            task_results = task.result.get("results", {})

        output_list: list[DeviceDeployResult] = []
        for dev_id in device_ids:
            dev = device_map.get(dev_id)

            # 从结果字典中获取详情
            res_entry = task_results.get(str(dev_id)) or {}

            # 状态映射
            status = res_entry.get("status", "pending")
            # 如果整个任务已失败且设备无结果，可能标记为 failed/skipped?
            # 暂时默认为 pending，除非明确有结果

            output_list.append(
                DeviceDeployResult(
                    device_id=dev_id,
                    device_name=dev.name if dev else None,
                    status=status,
                    output=res_entry.get("result"),  # Nornir result usually in 'result'
                    error=res_entry.get("error"),
                    executed_at=None,  # 暂无单设备执行时间
                )
            )

        return output_list

    @transactional()
    async def execute_task(self, task_id: UUID) -> Task:
        """执行下发任务（提交 Celery 前先做 OTP/凭据预检）。

        - 若存在 otp_manual 且 OTP 未缓存：直接置为 PAUSED，并返回 otp_required 信息（前端弹窗输入后再重试）。
        - 预检通过后：提交 Celery 并置为 RUNNING。
        """
        task = await self.get_task(task_id)

        if task.task_type != TaskType.DEPLOY.value:
            raise BadRequestException("仅支持下发任务")
        if task.approval_status != ApprovalStatus.APPROVED.value:
            raise BadRequestException("任务未审批通过")
        if task.status not in {TaskStatus.APPROVED.value, TaskStatus.PAUSED.value}:
            raise BadRequestException("非审批通过/暂停状态的任务不可执行")

        device_ids = self._get_target_device_ids(task)
        if not device_ids:
            raise BadRequestException("任务未包含目标设备")

        devices = await self.device_crud.get_multi_by_ids(self.db, ids=device_ids)
        devices = [d for d in devices if d.status == DeviceStatus.ACTIVE.value]
        if not devices:
            raise BadRequestException("没有可下发的设备")

        otp_required_groups: list[dict] = []
        for device in devices:
            auth_type = AuthType(device.auth_type)

            if auth_type == AuthType.STATIC:
                if not device.username or not device.password_encrypted:
                    raise BadRequestException(f"设备 {device.name} 缺少静态凭据配置")
                continue

            if not device.dept_id:
                raise BadRequestException(f"设备 {device.name} 缺少部门关联")

            credential = await self.credential_crud.get_by_dept_and_group(self.db, device.dept_id, device.device_group)
            if not credential:
                raise BadRequestException(f"设备 {device.name} 的设备组凭据未配置")

            if auth_type == AuthType.OTP_SEED:
                if not credential.username or not credential.otp_seed_encrypted:
                    raise BadRequestException(f"设备 {device.name} 的设备组 OTP 种子未配置")
                continue

            if auth_type == AuthType.OTP_MANUAL:
                if not credential.username:
                    raise BadRequestException(f"设备 {device.name} 的设备组账号未配置")
                cached = await otp_service.get_cached_otp(device.dept_id, device.device_group)
                if not cached:
                    otp_required_groups.append(
                        {
                            "dept_id": str(device.dept_id),
                            "device_group": device.device_group,
                        }
                    )
                continue

            raise BadRequestException(f"不支持的认证类型: {device.auth_type}")

        if otp_required_groups:
            # 去重 + 保持顺序
            seen: set[tuple[str, str]] = set()
            unique_groups: list[dict] = []
            for g in otp_required_groups:
                key = (g["dept_id"], g["device_group"])
                if key in seen:
                    continue
                seen.add(key)
                unique_groups.append(g)

            task.status = TaskStatus.PAUSED.value
            task.error_message = f"需要输入 OTP（共 {len(unique_groups)} 个设备分组）"
            task.result = {
                "otp_required": True,
                "otp_required_groups": unique_groups,
                "expires_in": 60,
                "next_action": "cache_otp_and_retry_execute",
            }
            await self.db.flush()
            await self.db.refresh(task)
            task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
            if not task_with_related:
                raise NotFoundException("任务不存在")
            return task_with_related

        from app.celery.tasks.deploy import async_deploy_task, deploy_task
        from app.core.config import settings

        # 重新执行：清理暂停原因/提示
        task.error_message = None
        task.result = None

        # 根据配置选择同步或异步任务
        if settings.USE_ASYNC_NETWORK_TASKS:
            celery_result = async_deploy_task.delay(task_id=str(task_id))  # type: ignore[attr-defined]
        else:
            celery_result = deploy_task.delay(task_id=str(task_id))  # type: ignore[attr-defined]
        task.celery_task_id = celery_result.id
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def create_deploy_task(self, data: DeployCreateRequest, *, submitter_id: UUID) -> Task:
        if data.approver_ids is not None and len(data.approver_ids) != 3:
            raise BadRequestException("approver_ids 必须为 3 个（三级审批）")

        task = Task(
            name=data.name,
            task_type=TaskType.DEPLOY.value,
            description=data.description,
            status=TaskStatus.PENDING.value,
            approval_status=ApprovalStatus.PENDING.value,
            approval_required=True,
            current_approval_level=0,
            target_devices={"device_ids": [str(x) for x in data.device_ids]},
            total_devices=len(data.device_ids),
            success_count=0,
            failed_count=0,
            template_id=data.template_id,
            template_params=data.template_params,
            deploy_plan=data.deploy_plan.model_dump(),
            change_description=data.change_description,
            impact_scope=data.impact_scope,
            rollback_plan=data.rollback_plan,
            submitter_id=submitter_id,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        # 创建三级审批步骤（默认 PENDING）
        for idx in range(3):
            approver_id = data.approver_ids[idx] if data.approver_ids else None
            step = TaskApprovalStep(
                task_id=task.id,
                level=idx + 1,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
            )
            self.db.add(step)

        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def approve_step(
        self,
        task_id: UUID,
        *,
        level: int,
        approve: bool,
        comment: str | None,
        actor_user_id: UUID,
        is_superuser: bool = False,
    ) -> Task:
        task = await self.get_task(task_id)
        if task.task_type != TaskType.DEPLOY.value:
            raise BadRequestException("仅下发任务支持审批")

        if task.approval_status in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}:
            raise BadRequestException("任务已完成审批，不可重复审批")

        if level != task.current_approval_level + 1:
            raise BadRequestException("请按顺序审批（必须审批当前级别）")

        step = await self.task_approval_crud.get_by_task_and_level(self.db, task_id=task.id, level=level)
        if not step:
            raise NotFoundException("审批步骤不存在")

        if step.approver_id and step.approver_id != actor_user_id and not is_superuser:
            raise ForbiddenException("当前用户不是该级审批人")

        # 未指定审批人时，记录实际审批账号
        if step.approver_id is None:
            step.approver_id = actor_user_id
        elif step.approver_id != actor_user_id and is_superuser:
            # 超级管理员代审：以实际操作账号为准
            step.approver_id = actor_user_id

        step.status = ApprovalStatus.APPROVED.value if approve else ApprovalStatus.REJECTED.value
        step.comment = comment
        step.approved_at = datetime.now(UTC)

        if approve:
            task.current_approval_level = level
            if level >= 3:
                task.approval_status = ApprovalStatus.APPROVED.value
                task.status = TaskStatus.APPROVED.value
        else:
            task.approval_status = ApprovalStatus.REJECTED.value
            task.status = TaskStatus.REJECTED.value

        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def bind_celery_task(self, task_id: UUID, celery_task_id: str) -> Task:
        task = await self.get_task(task_id)
        task.celery_task_id = celery_task_id
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def mark_paused(self, task_id: UUID, *, reason: str, details: dict | None = None) -> Task:
        task = await self.get_task(task_id)
        task.status = TaskStatus.PAUSED.value
        task.error_message = reason
        task.result = details or {}
        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def mark_finished(
        self, task_id: UUID, *, success: bool, result: dict | None = None, error: str | None = None
    ):
        task = await self.get_task(task_id)
        task.status = TaskStatus.SUCCESS.value if success else TaskStatus.FAILED.value
        task.finished_at = datetime.now(UTC)
        task.result = result
        task.error_message = error
        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def cancel_task(self, task_id: UUID) -> Task:
        """取消正在执行的任务。

        仅 RUNNING 状态可取消。会尝试终止 Celery 任务。
        """
        task = await self.get_task(task_id)

        if task.status not in {TaskStatus.RUNNING.value, TaskStatus.PAUSED.value}:
            raise BadRequestException(f"任务状态为 {task.status}，无法取消（仅执行中或暂停的任务可取消）")

        # 尝试撤销 Celery 任务（不使用 terminate，因为 ThreadPool 不支持）
        # 任务会在下次执行时检查状态并跳过
        if task.celery_task_id:
            try:
                from app.celery.app import celery_app

                # 仅 revoke，不 terminate（ThreadPool 不支持 kill_job）
                celery_app.control.revoke(task.celery_task_id)
            except Exception as e:
                # 即使 Celery 撤销失败，仍然更新状态
                from app.core.logger import logger

                logger.warning(f"撤销 Celery 任务失败: {e}", task_id=str(task_id))

        task.status = TaskStatus.CANCELLED.value
        task.finished_at = datetime.now(UTC)
        task.error_message = "任务已被用户取消"

        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related

    @transactional()
    async def retry_failed_devices(self, task_id: UUID) -> Task:
        """重试失败的设备。

        仅 PARTIAL 或 FAILED 状态可重试。
        """
        task = await self.get_task(task_id)

        if task.status not in {TaskStatus.PARTIAL.value, TaskStatus.FAILED.value}:
            raise BadRequestException(f"任务状态为 {task.status}，无法重试（仅部分成功或失败的任务可重试）")

        # 提取失败的设备 ID
        failed_device_ids: list[str] = []
        if task.result and isinstance(task.result, dict):
            results = task.result.get("results", {})
            for device_id, res in results.items():
                if isinstance(res, dict) and res.get("status") != "success":
                    failed_device_ids.append(device_id)

        # 如果没有从 results 中找到失败设备，但任务状态是 FAILED，
        # 可能是任务执行前就失败了（如凭据问题），此时重试所有目标设备
        if not failed_device_ids and task.status == TaskStatus.FAILED.value:
            # 回退到原始目标设备列表
            original_device_ids = self._get_target_device_ids(task)
            failed_device_ids = [str(d) for d in original_device_ids]

        if not failed_device_ids:
            raise BadRequestException("没有需要重试的失败设备")

        # 更新 target_devices 仅包含失败设备
        task.target_devices = {"device_ids": failed_device_ids}
        task.total_devices = len(failed_device_ids)
        task.success_count = 0
        task.failed_count = 0
        task.progress = 0
        task.error_message = None
        # 保留原有结果用于审计，但清除以便重新执行
        # task.result = None  # 可选：是否清除

        # 重新提交执行
        from app.celery.tasks.deploy import async_deploy_task, deploy_task
        from app.core.config import settings

        if settings.USE_ASYNC_NETWORK_TASKS:
            celery_result = async_deploy_task.delay(task_id=str(task_id))  # type: ignore[attr-defined]
        else:
            celery_result = deploy_task.delay(task_id=str(task_id))  # type: ignore[attr-defined]

        task.celery_task_id = celery_result.id
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(UTC)
        task.finished_at = None

        await self.db.flush()
        await self.db.refresh(task)
        task_with_related = await self.task_crud.get_with_related(self.db, id=task.id)
        if not task_with_related:
            raise NotFoundException("任务不存在")
        return task_with_related
