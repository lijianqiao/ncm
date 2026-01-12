"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_service.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template 业务服务。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import ApprovalStatus, TemplateStatus
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.crud.crud_template import CRUDTemplate
from app.crud.crud_template_approval import CRUDTemplateApprovalStep
from app.models.template import Template
from app.models.template_approval import TemplateApprovalStep
from app.schemas.template import TemplateCreate, TemplateUpdate


class TemplateService:
    def __init__(self, db: AsyncSession, template_crud: CRUDTemplate, template_approval_crud: CRUDTemplateApprovalStep):
        self.db = db
        self.template_crud = template_crud
        self.template_approval_crud = template_approval_crud

    async def get_templates_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        vendor: str | None = None,
        template_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Template], int]:
        return await self.template_crud.get_multi_paginated_filtered(
            self.db,
            page=page,
            page_size=page_size,
            vendor=vendor,
            template_type=template_type,
            status=status,
        )

    async def get_template(self, template_id: UUID):
        template = await self.template_crud.get(self.db, id=template_id)
        if not template:
            raise NotFoundException("模板不存在")
        return template

    @transactional()
    async def delete_template(self, template_id: UUID):
        deleted = await self.template_crud.remove(self.db, id=template_id)
        if not deleted:
            raise NotFoundException("模板不存在")
        return deleted

    @transactional()
    async def create_template(self, data: TemplateCreate, creator_id: UUID):
        create_data = data.model_dump()
        obj = Template(
            name=create_data["name"],
            description=create_data.get("description"),
            template_type=data.template_type.value,
            content=create_data["content"],
            vendors=[v.value for v in data.vendors],
            device_type=data.device_type.value,
            parameters=create_data.get("parameters"),
            creator_id=creator_id,
            approval_required=True,
            approval_status=ApprovalStatus.NONE.value,
            current_approval_level=0,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @transactional()
    async def update_template(self, template_id: UUID, data: TemplateUpdate):
        template = await self.get_template(template_id)
        update_data = data.model_dump(exclude_unset=True)
        if "vendors" in update_data and update_data["vendors"] is not None:
            update_data["vendors"] = [v.value for v in update_data["vendors"]]
        if "template_type" in update_data and update_data["template_type"] is not None:
            update_data["template_type"] = update_data["template_type"].value
        if "device_type" in update_data and update_data["device_type"] is not None:
            update_data["device_type"] = update_data["device_type"].value
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value

        return await self.template_crud.update(self.db, db_obj=template, obj_in=update_data)

    @transactional()
    async def new_version(self, template_id: UUID, *, name: str | None = None, description: str | None = None):
        base = await self.get_template(template_id)
        if base.status not in {
            TemplateStatus.APPROVED.value,
            TemplateStatus.DEPRECATED.value,
            TemplateStatus.DRAFT.value,
        }:
            # 允许草稿/已审批/已废弃派生新版本，避免复杂状态机
            raise BadRequestException("当前模板状态不允许创建新版本")

        parent_id = base.parent_id or base.id
        latest = await self.template_crud.get_latest_by_parent(self.db, parent_id)
        next_version = (latest.version if latest else base.version) + 1

        obj = Template(
            name=name or base.name,
            description=description if description is not None else base.description,
            template_type=base.template_type,
            content=base.content,
            vendors=base.vendors,
            device_type=base.device_type,
            parameters=base.parameters,
            version=next_version,
            parent_id=parent_id,
            status=TemplateStatus.DRAFT.value,
            creator_id=base.creator_id,
            approval_required=True,
            approval_status=ApprovalStatus.NONE.value,
            current_approval_level=0,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @transactional()
    async def submit(
        self,
        template_id: UUID,
        *,
        comment: str | None = None,
        approver_ids: list[UUID] | None = None,
    ):
        template = await self.get_template(template_id)
        if template.status not in {TemplateStatus.DRAFT.value, TemplateStatus.REJECTED.value}:
            raise BadRequestException("仅草稿/已拒绝模板可提交审批")

        if approver_ids is not None and len(approver_ids) != 3:
            raise BadRequestException("approver_ids 必须为 3 个（三级审批）")

        # 清理旧审批步骤（允许驳回后重新提交）
        for step in list(template.approval_steps or []):
            await self.db.delete(step)

        template.status = TemplateStatus.PENDING.value
        template.approval_required = True
        template.approval_status = ApprovalStatus.PENDING.value
        template.current_approval_level = 0
        if comment:
            # 简单写入 description 末尾，避免新增字段
            template.description = (template.description or "") + f"\n[submit] {comment}"

        # 创建三级审批步骤（默认 PENDING）
        for idx in range(3):
            approver_id = approver_ids[idx] if approver_ids else None
            step = TemplateApprovalStep(
                template_id=template.id,
                level=idx + 1,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
            )
            self.db.add(step)

        await self.db.flush()
        # 重要：updated_at 是数据库侧 onupdate 生成，flush 后需要 refresh，避免响应序列化时触发懒加载导致 MissingGreenlet
        await self.db.refresh(template)
        return template

    @transactional()
    async def approve_step(
        self,
        template_id: UUID,
        *,
        level: int,
        approve: bool,
        comment: str | None,
        actor_user_id: UUID,
        is_superuser: bool = False,
    ) -> Template:
        template = await self.get_template(template_id)

        if template.approval_status in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}:
            raise BadRequestException("模板已完成审批，不可重复审批")

        if template.status != TemplateStatus.PENDING.value or template.approval_status != ApprovalStatus.PENDING.value:
            raise BadRequestException("模板不在审批阶段")

        if level != (template.current_approval_level or 0) + 1:
            raise BadRequestException("请按顺序审批（必须审批当前级别）")

        step = await self.template_approval_crud.get_by_template_and_level(
            self.db, template_id=template.id, level=level
        )
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
            template.current_approval_level = level
            if level >= 3:
                template.approval_status = ApprovalStatus.APPROVED.value
                template.status = TemplateStatus.APPROVED.value
        else:
            template.approval_status = ApprovalStatus.REJECTED.value
            template.status = TemplateStatus.REJECTED.value

        await self.db.flush()
        await self.db.refresh(template)
        return template
