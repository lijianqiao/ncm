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
from app.core.enums import ApprovalStatus, TaskStatus, TaskType
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.crud.crud_task import CRUDTask
from app.crud.crud_task_approval import CRUDTaskApprovalStep
from app.models.task import Task
from app.models.task_approval import TaskApprovalStep
from app.schemas.deploy import DeployCreateRequest


class DeployService:
    def __init__(
        self,
        db: AsyncSession,
        task_crud: CRUDTask,
        task_approval_crud: CRUDTaskApprovalStep,
    ):
        self.db = db
        self.task_crud = task_crud
        self.task_approval_crud = task_approval_crud

    async def get_task(self, task_id: UUID) -> Task:
        task = await self.task_crud.get_with_related(self.db, id=task_id)
        if not task:
            raise NotFoundException("任务不存在")
        return task

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
