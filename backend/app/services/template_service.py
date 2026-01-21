"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_service.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template 业务服务。
"""

import json
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
        return await self.template_crud.get_multi_paginated(
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
        template = await self.template_crud.get(self.db, id=template_id)
        if not template:
            raise NotFoundException("模板不存在")
        success_count, _ = await self.template_crud.batch_remove(self.db, ids=[template_id])
        if success_count == 0:
            raise NotFoundException("模板不存在")
        # 刷新对象以获取最新状态（包括 is_deleted=True 和 updated_at）
        await self.db.refresh(template)
        return template

    @transactional()
    async def batch_delete_templates(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """批量删除模板（软删除）。"""
        return await self.template_crud.batch_remove(self.db, ids=ids, hard_delete=False)

    async def get_recycle_bin_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[Template], int]:
        """获取回收站模板列表（分页）。"""
        return await self.template_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
        )

    @transactional()
    async def restore_template(self, template_id: UUID) -> Template:
        """恢复已删除的模板。"""
        template = await self.template_crud.get_deleted(self.db, id=template_id)
        if not template:
            raise NotFoundException("模板不存在或未被删除")

        success_count, _ = await self.template_crud.batch_restore(self.db, ids=[template_id])
        if success_count == 0:
            raise NotFoundException("恢复失败")

        await self.db.refresh(template)
        return template

    @transactional()
    async def batch_restore_templates(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """批量恢复已删除的模板。"""
        return await self.template_crud.batch_restore(self.db, ids=ids)

    @transactional()
    async def hard_delete_template(self, template_id: UUID) -> None:
        """彻底删除模板（硬删除）。"""
        template = await self.template_crud.get_deleted(self.db, id=template_id)
        if not template:
            raise NotFoundException("模板不存在或未被软删除")

        success_count, _ = await self.template_crud.batch_remove(self.db, ids=[template_id], hard_delete=True)
        if success_count == 0:
            raise NotFoundException("彻底删除失败")

    @transactional()
    async def batch_hard_delete_templates(self, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """批量彻底删除模板（硬删除）。"""
        return await self.template_crud.batch_remove(self.db, ids=ids, hard_delete=True)

    @transactional()
    async def create_template(self, data: TemplateCreate, creator_id: UUID) -> Template:
        """创建模板草稿。"""
        # 校验 parameters 必须是有效的 JSON Schema
        parameters = data.parameters
        if parameters:
            try:
                schema = json.loads(parameters)
                if not isinstance(schema, dict) or "type" not in schema:
                    raise BadRequestException("parameters 必须是包含 type 字段的有效 JSON Schema 对象")
            except json.JSONDecodeError as e:
                raise BadRequestException(f"parameters 不是合法 JSON: {e}") from e
        else:
            # 默认填充空 Schema（允许任意参数）
            parameters = '{"type": "object"}'

        obj = Template(
            name=data.name,
            description=data.description,
            template_type=data.template_type.value,
            content=data.content,
            vendors=[v.value for v in data.vendors],
            device_type=data.device_type.value,
            parameters=parameters,
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
    async def new_version(
        self, template_id: UUID, *, name: str | None = None, description: str | None = None
    ) -> Template:
        """基于现有模板创建新版本（草稿）。"""
        base = await self.get_template(template_id)

        # 允许草稿/已审批/已废弃派生新版本
        allowed_statuses = {
            TemplateStatus.APPROVED.value,
            TemplateStatus.DEPRECATED.value,
            TemplateStatus.DRAFT.value,
        }
        if base.status not in allowed_statuses:
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
    ) -> Template:
        """提交模板审批。"""
        template = await self.get_template(template_id)

        allowed_statuses = {TemplateStatus.DRAFT.value, TemplateStatus.REJECTED.value}
        if template.status not in allowed_statuses:
            raise BadRequestException("仅草稿/已拒绝模板可提交审批")

        if approver_ids is not None and len(approver_ids) != 3:
            raise BadRequestException("approver_ids 必须为 3 个（三级审批）")

        # 清理旧审批步骤（允许驳回后重新提交）- 使用批量硬删除
        if template.approval_steps:
            old_step_ids = [step.id for step in template.approval_steps]
            await self.template_approval_crud.batch_remove(self.db, ids=old_step_ids, hard_delete=True)

        # 更新模板状态
        template.status = TemplateStatus.PENDING.value
        template.approval_required = True
        template.approval_status = ApprovalStatus.PENDING.value
        template.current_approval_level = 0
        if comment:
            # 简单写入 description 末尾，避免新增字段
            template.description = (template.description or "") + f"\n[submit] {comment}"

        # 创建三级审批步骤（默认 PENDING）
        for level in range(1, 4):
            approver_id = approver_ids[level - 1] if approver_ids else None
            step = TemplateApprovalStep(
                template_id=template.id,
                level=level,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
            )
            self.db.add(step)

        await self.db.flush()
        # 重要：updated_at 是数据库侧 onupdate 生成，flush 后需要 refresh
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
