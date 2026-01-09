"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template_service.py
@DateTime: 2026-01-09 23:00:00
@Docs: Template 业务服务。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import TemplateStatus
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_template import CRUDTemplate
from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate


class TemplateService:
    def __init__(self, db: AsyncSession, template_crud: CRUDTemplate):
        self.db = db
        self.template_crud = template_crud

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

    async def get_template(self, template_id):
        template = await self.template_crud.get(self.db, id=template_id)
        if not template:
            raise NotFoundException("模板不存在")
        return template

    @transactional()
    async def delete_template(self, template_id):
        deleted = await self.template_crud.remove(self.db, id=template_id)
        if not deleted:
            raise NotFoundException("模板不存在")
        return deleted

    @transactional()
    async def create_template(self, data: TemplateCreate, creator_id):
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
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @transactional()
    async def update_template(self, template_id, data: TemplateUpdate):
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
    async def new_version(self, template_id, *, name: str | None = None, description: str | None = None):
        base = await self.get_template(template_id)
        if base.status not in {TemplateStatus.APPROVED.value, TemplateStatus.DEPRECATED.value, TemplateStatus.DRAFT.value}:
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
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @transactional()
    async def submit(self, template_id, *, comment: str | None = None):
        template = await self.get_template(template_id)
        if template.status != TemplateStatus.DRAFT.value:
            raise BadRequestException("仅草稿模板可提交审批")
        # Phase 4 仅实现提交状态，真正审批可以复用 TaskApprovalStep 或后续扩展
        template.status = TemplateStatus.PENDING.value
        if comment:
            # 简单写入 description 末尾，避免新增字段
            template.description = (template.description or "") + f"\n[submit] {comment}"
        await self.db.flush()
        return template

