"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy_service.py
@DateTime: 2026-01-09 23:40:00
@Docs: 安全批量下发服务（任务创建/审批/执行/回滚入口）。
"""

from datetime import UTC, datetime
from uuid import UUID

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
        return task

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
            raise BadRequestException("任务当前状态不可执行")

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

        from app.celery.tasks.deploy import deploy_task

        # 重新执行：清理暂停原因/提示
        task.error_message = None
        task.result = None

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
