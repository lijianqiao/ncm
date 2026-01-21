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

from jinja2 import Environment, TemplateSyntaxError, meta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import ApprovalStatus, ParamType, TemplateStatus
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.crud.crud_template import CRUDTemplate
from app.crud.crud_template_approval import CRUDTemplateApprovalStep
from app.crud.crud_template_parameter import CRUDTemplateParameter
from app.models.template import Template
from app.models.template_approval import TemplateApprovalStep
from app.models.template_parameter import TemplateParameter
from app.schemas.template import (
    ExtractedVariable,
    TemplateCreate,
    TemplateCreateV2,
    TemplateParameterCreate,
    TemplateUpdate,
    TemplateUpdateV2,
)


class TemplateService:
    def __init__(
        self,
        db: AsyncSession,
        template_crud: CRUDTemplate,
        template_approval_crud: CRUDTemplateApprovalStep,
        template_parameter_crud: CRUDTemplateParameter | None = None,
    ):
        self.db = db
        self.template_crud = template_crud
        self.template_approval_crud = template_approval_crud
        self.template_parameter_crud = template_parameter_crud

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

    # ===== V2 表单化参数相关方法 =====

    @staticmethod
    def extract_variables(content: str) -> list[str]:
        """
        从 Jinja2 模板内容中提取变量名。

        Args:
            content: Jinja2 模板内容

        Returns:
            变量名列表（已排序）

        Raises:
            BadRequestException: 模板语法错误
        """
        env = Environment()
        try:
            ast = env.parse(content)
            variables = meta.find_undeclared_variables(ast)
            # 过滤掉常见的内置变量
            filtered = {v for v in variables if not v.startswith("_") and v not in {"device", "params"}}
            return sorted(filtered)
        except TemplateSyntaxError as e:
            raise BadRequestException(f"Jinja2 模板语法错误: {e}") from e

    @staticmethod
    def _guess_param_type(var_name: str) -> ParamType:
        """
        根据变量名智能推断参数类型。

        Args:
            var_name: 变量名

        Returns:
            推断的参数类型
        """
        name = var_name.lower()

        # VLAN 相关
        if "vlan" in name and ("id" in name or name == "vlan"):
            return ParamType.VLAN_ID

        # IP 地址相关
        if "ip" in name or "address" in name:
            if "cidr" in name or "prefix" in name or "mask" in name:
                return ParamType.CIDR
            return ParamType.IP_ADDRESS

        # 接口相关
        if "interface" in name or "port_name" in name or name in {"intf", "port"}:
            return ParamType.INTERFACE

        # MAC 地址相关
        if "mac" in name:
            return ParamType.MAC_ADDRESS

        # 端口号相关
        if name in {"port", "port_number"} or name.endswith("_port"):
            return ParamType.PORT

        # 整数类型
        if name.endswith("_id") or "count" in name or "number" in name or "num" in name:
            return ParamType.INTEGER

        # 布尔类型
        if name.startswith("is_") or name.startswith("enable") or name.startswith("has_"):
            return ParamType.BOOLEAN

        # 默认字符串
        return ParamType.STRING

    @staticmethod
    def _var_to_label(var_name: str) -> str:
        """
        将变量名转换为显示名称。

        Args:
            var_name: 变量名（如 vlan_id）

        Returns:
            显示名称（如 Vlan Id）
        """
        return var_name.replace("_", " ").title()

    def auto_generate_parameters(self, content: str) -> list[ExtractedVariable]:
        """
        自动从模板内容提取变量并生成参数定义骨架。

        Args:
            content: Jinja2 模板内容

        Returns:
            提取的变量列表（含推断类型）
        """
        variables = self.extract_variables(content)
        return [
            ExtractedVariable(
                name=var,
                label=self._var_to_label(var),
                param_type=self._guess_param_type(var),
                required=True,
            )
            for var in variables
        ]

    @staticmethod
    def parameters_to_json_schema(params: list[TemplateParameter] | list[TemplateParameterCreate]) -> str:
        """
        将表单化参数列表转换为 JSON Schema 字符串。

        Args:
            params: 参数列表

        Returns:
            JSON Schema 字符串
        """
        # 类型映射
        type_mapping: dict[str, dict] = {
            ParamType.STRING.value: {"type": "string"},
            ParamType.INTEGER.value: {"type": "integer"},
            ParamType.BOOLEAN.value: {"type": "boolean"},
            ParamType.SELECT.value: {"type": "string"},
            ParamType.IP_ADDRESS.value: {"type": "string", "format": "ipv4"},
            ParamType.CIDR.value: {"type": "string", "pattern": r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$"},
            ParamType.VLAN_ID.value: {"type": "integer", "minimum": 1, "maximum": 4094},
            ParamType.INTERFACE.value: {"type": "string"},
            ParamType.MAC_ADDRESS.value: {"type": "string", "pattern": r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"},
            ParamType.PORT.value: {"type": "integer", "minimum": 1, "maximum": 65535},
        }

        properties: dict[str, dict] = {}
        required: list[str] = []

        for p in params:
            # 获取参数类型值
            param_type_value = p.param_type.value if isinstance(p.param_type, ParamType) else p.param_type
            prop = type_mapping.get(param_type_value, {"type": "string"}).copy()

            # 获取参数属性
            description = p.description
            default_value = p.default_value
            options = p.options
            min_value = p.min_value
            max_value = p.max_value
            pattern = p.pattern
            is_required = p.required

            if description:
                prop["description"] = description
            if default_value is not None:
                # 尝试类型转换
                if prop.get("type") == "integer":
                    try:
                        prop["default"] = int(default_value)
                    except ValueError:
                        prop["default"] = default_value
                elif prop.get("type") == "boolean":
                    prop["default"] = default_value.lower() in ("true", "1", "yes")
                else:
                    prop["default"] = default_value
            if options:
                prop["enum"] = options
            if min_value is not None:
                prop["minimum"] = min_value
            if max_value is not None:
                prop["maximum"] = max_value
            if pattern:
                prop["pattern"] = pattern

            properties[p.name] = prop
            if is_required:
                required.append(p.name)

        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        return json.dumps(schema, ensure_ascii=False)

    @transactional()
    async def create_template_v2(self, data: TemplateCreateV2, creator_id: UUID) -> Template:
        """
        创建模板草稿（V2 - 表单化参数）。

        Args:
            data: 创建模板请求体（含表单化参数）
            creator_id: 创建人 ID

        Returns:
            创建的模板对象
        """
        # 将表单化参数转换为 JSON Schema
        parameters = self.parameters_to_json_schema(data.parameters_list)

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

        # 创建参数记录
        if data.parameters_list and self.template_parameter_crud:
            await self.template_parameter_crud.create_for_template(
                self.db,
                template_id=obj.id,
                params=data.parameters_list,
            )
            await self.db.refresh(obj)

        return obj

    @transactional()
    async def update_template_v2(self, template_id: UUID, data: TemplateUpdateV2) -> Template:
        """
        更新模板（V2 - 表单化参数）。

        Args:
            template_id: 模板 ID
            data: 更新模板请求体

        Returns:
            更新后的模板对象
        """
        template = await self.get_template(template_id)
        update_data = data.model_dump(exclude_unset=True, exclude={"parameters_list"})

        # 枚举类型转换
        if "vendors" in update_data and update_data["vendors"] is not None:
            update_data["vendors"] = [v.value for v in update_data["vendors"]]
        if "template_type" in update_data and update_data["template_type"] is not None:
            update_data["template_type"] = update_data["template_type"].value
        if "device_type" in update_data and update_data["device_type"] is not None:
            update_data["device_type"] = update_data["device_type"].value
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value

        # 如果提供了参数列表，同步参数并更新 JSON Schema
        if data.parameters_list is not None and self.template_parameter_crud:
            await self.template_parameter_crud.sync_parameters(
                self.db,
                template_id=template_id,
                params=data.parameters_list,
            )
            update_data["parameters"] = self.parameters_to_json_schema(data.parameters_list)

        if update_data:
            template = await self.template_crud.update(self.db, db_obj=template, obj_in=update_data)

        await self.db.refresh(template)
        return template
