"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: template.py
@DateTime: 2026-01-09 23:00:00
@Docs: 配置模板 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ApprovalStatus, DeviceType, DeviceVendor, ParamType, TemplateStatus, TemplateType
from app.schemas.common import PaginatedQuery


class TemplateApprovalRecord(BaseModel):
    """模板审批记录 Schema（单级）。

    用于表示模板的单个审批级别记录。

    Attributes:
        level (int): 审批级别（1-3）。
        approver_id (UUID | None): 审批人 ID。
        approver_name (str | None): 审批人名称。
        status (ApprovalStatus): 审批状态，默认 PENDING。
        comment (str | None): 审批意见。
        approved_at (datetime | None): 审批时间。
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    level: int
    approver_id: UUID | None = None
    approver_name: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    comment: str | None = None
    approved_at: datetime | None = None


class TemplateBase(BaseModel):
    """模板基础 Schema。

    模板的基础字段定义，用于创建和更新模板。

    Attributes:
        name (str): 模板名称。
        description (str | None): 模板描述。
        template_type (TemplateType): 模板类型，默认 CUSTOM。
        content (str): Jinja2 模板内容。
        vendors (list[DeviceVendor]): 适用厂商列表，至少包含 1 个。
        device_type (DeviceType): 适用设备类型，默认 ALL。
        parameters (str | None): 参数定义（JSON Schema 字符串）。
    """

    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType = Field(default=TemplateType.CUSTOM, description="模板类型")
    content: str = Field(..., min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] = Field(..., min_length=1, description="适用厂商列表")
    device_type: DeviceType = Field(default=DeviceType.ALL, description="适用设备类型")
    parameters: str | None = Field(default=None, description="参数定义(JSON Schema 字符串)")


class TemplateCreate(TemplateBase):
    """创建模板请求 Schema。

    用于创建新模板的请求体，继承自 TemplateBase。
    """

    pass


class TemplateUpdate(BaseModel):
    """更新模板请求 Schema（字段均可选）。

    用于更新模板信息的请求体，所有字段可选。

    Attributes:
        name (str | None): 模板名称。
        description (str | None): 模板描述。
        template_type (TemplateType | None): 模板类型。
        content (str | None): Jinja2 模板内容。
        vendors (list[DeviceVendor] | None): 适用厂商列表。
        device_type (DeviceType | None): 适用设备类型。
        parameters (str | None): 参数定义（JSON Schema 字符串）。
        status (TemplateStatus | None): 模板状态。
    """

    name: str | None = Field(default=None, min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType | None = Field(default=None, description="模板类型")
    content: str | None = Field(default=None, min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] | None = Field(default=None, min_length=1, description="适用厂商列表")
    device_type: DeviceType | None = Field(default=None, description="适用设备类型")
    parameters: str | None = Field(default=None, description="参数定义(JSON Schema 字符串)")
    status: TemplateStatus | None = Field(default=None, description="模板状态")


class TemplateResponse(BaseModel):
    """模板响应 Schema。

    用于返回模板完整信息的响应体，包含审批记录。

    Attributes:
        id (UUID): 模板 ID。
        name (str): 模板名称。
        description (str | None): 模板描述。
        template_type (TemplateType): 模板类型。
        content (str): Jinja2 模板内容。
        vendors (list[DeviceVendor]): 适用厂商列表。
        device_type (DeviceType): 适用设备类型。
        parameters (str | None): 参数定义（JSON Schema 字符串）。
        version (int): 版本号。
        parent_id (UUID | None): 父版本 ID。
        status (TemplateStatus): 模板状态。
        creator_id (UUID | None): 创建人 ID。
        created_by (UUID | None): 创建人 ID（兼容字段）。
        created_by_name (str | None): 创建人名称。
        usage_count (int): 使用次数。
        approval_status (ApprovalStatus | None): 审批状态。
        current_approval_level (int | None): 当前已通过的审批级别。
        approvals (list[TemplateApprovalRecord]): 审批记录列表。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    name: str
    description: str | None = None
    template_type: TemplateType
    content: str
    vendors: list[DeviceVendor]
    device_type: DeviceType
    parameters: str | None = None
    version: int
    parent_id: UUID | None = None
    status: TemplateStatus
    creator_id: UUID | None = None
    created_by: UUID | None = None
    created_by_name: str | None = None
    usage_count: int
    approval_status: ApprovalStatus | None = None
    current_approval_level: int | None = None
    approvals: list[TemplateApprovalRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TemplateListQuery(PaginatedQuery):
    """模板列表查询参数 Schema。

    用于模板列表查询的请求参数，包含分页和筛选条件。

    Attributes:
        vendor (DeviceVendor | None): 厂商筛选。
        template_type (TemplateType | None): 模板类型筛选。
        status (TemplateStatus | None): 模板状态筛选。
    """

    vendor: DeviceVendor | None = None
    template_type: TemplateType | None = None
    status: TemplateStatus | None = None


class TemplateNewVersionRequest(BaseModel):
    """基于某个模板版本创建新版本请求 Schema。

    用于基于现有模板版本创建新版本的请求体。

    Attributes:
        name (str | None): 新版本名称（可选）。
        description (str | None): 新版本描述（可选）。
    """

    name: str | None = Field(default=None, description="新版本名称(可选)")
    description: str | None = Field(default=None, description="新版本描述(可选)")


class TemplateSubmitRequest(BaseModel):
    """提交模板审批请求 Schema。

    用于提交模板审批的请求体。

    Attributes:
        comment (str | None): 提交说明（可选）。
        approver_ids (list[UUID] | None): 三级审批人 ID 列表（长度=3，可选）。
    """

    comment: str | None = Field(default=None, description="提交说明(可选)")
    approver_ids: list[UUID] | None = Field(default=None, description="三级审批人ID列表（长度=3，可选）")


class TemplateApproveRequest(BaseModel):
    """审批某一级请求 Schema。

    用于审批模板某一级别的请求体。

    Attributes:
        level (int): 审批级别（1-3）。
        approve (bool): 是否通过（true=通过，false=拒绝）。
        comment (str | None): 审批意见。
    """

    level: int = Field(..., ge=1, le=3)
    approve: bool = Field(..., description="true=通过 false=拒绝")
    comment: str | None = None


class TemplateBatchRequest(BaseModel):
    """模板批量操作请求。"""

    ids: list[UUID] = Field(..., min_length=1, description="模板ID列表")


class TemplateBatchResult(BaseModel):
    """模板批量操作结果。"""

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="失败的ID列表")


# ===== V2 表单化参数相关 Schema =====


class TemplateParameterBase(BaseModel):
    """模板参数基础字段。"""

    name: str = Field(..., min_length=1, max_length=50, description="变量名（用于 Jinja2）")
    label: str = Field(..., min_length=1, max_length=100, description="显示名称")
    param_type: ParamType = Field(default=ParamType.STRING, description="参数类型")
    required: bool = Field(default=True, description="是否必填")
    default_value: str | None = Field(default=None, max_length=500, description="默认值")
    description: str | None = Field(default=None, description="参数说明")
    options: list[str] | None = Field(default=None, description="下拉选项（select 类型时使用）")
    min_value: int | None = Field(default=None, description="最小值（数值类型）")
    max_value: int | None = Field(default=None, description="最大值（数值类型）")
    pattern: str | None = Field(default=None, max_length=200, description="正则校验表达式")
    order: int = Field(default=0, ge=0, description="显示顺序")


class TemplateParameterCreate(TemplateParameterBase):
    """创建模板参数请求体。"""

    pass


class TemplateParameterUpdate(BaseModel):
    """更新模板参数请求体（字段均可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=50, description="变量名")
    label: str | None = Field(default=None, min_length=1, max_length=100, description="显示名称")
    param_type: ParamType | None = Field(default=None, description="参数类型")
    required: bool | None = Field(default=None, description="是否必填")
    default_value: str | None = Field(default=None, max_length=500, description="默认值")
    description: str | None = Field(default=None, description="参数说明")
    options: list[str] | None = Field(default=None, description="下拉选项")
    min_value: int | None = Field(default=None, description="最小值")
    max_value: int | None = Field(default=None, description="最大值")
    pattern: str | None = Field(default=None, max_length=200, description="正则校验表达式")
    order: int | None = Field(default=None, ge=0, description="显示顺序")


class TemplateParameterResponse(BaseModel):
    """模板参数响应体。"""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    template_id: UUID
    name: str
    label: str
    param_type: ParamType
    required: bool
    default_value: str | None = None
    description: str | None = None
    options: list[str] | None = None
    min_value: int | None = None
    max_value: int | None = None
    pattern: str | None = None
    order: int
    created_at: datetime
    updated_at: datetime


class TemplateCreateV2(BaseModel):
    """创建模板请求体（V2 - 表单化参数）。"""

    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType = Field(default=TemplateType.CUSTOM, description="模板类型")
    content: str = Field(..., min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] = Field(..., min_length=1, description="适用厂商列表")
    device_type: DeviceType = Field(default=DeviceType.ALL, description="适用设备类型")
    parameters_list: list[TemplateParameterCreate] = Field(
        default_factory=list, description="表单化参数列表"
    )


class TemplateUpdateV2(BaseModel):
    """更新模板请求体（V2 - 表单化参数，字段均可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType | None = Field(default=None, description="模板类型")
    content: str | None = Field(default=None, min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] | None = Field(default=None, min_length=1, description="适用厂商列表")
    device_type: DeviceType | None = Field(default=None, description="适用设备类型")
    parameters_list: list[TemplateParameterCreate] | None = Field(default=None, description="表单化参数列表")
    status: TemplateStatus | None = Field(default=None, description="模板状态")


class TemplateResponseV2(BaseModel):
    """模板响应体（V2 - 包含表单化参数）。"""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    name: str
    description: str | None = None
    template_type: TemplateType
    content: str
    vendors: list[DeviceVendor]
    device_type: DeviceType
    parameters: str | None = None
    parameters_list: list[TemplateParameterResponse] = Field(default_factory=list, description="表单化参数列表")
    version: int
    parent_id: UUID | None = None
    status: TemplateStatus
    creator_id: UUID | None = None
    created_by: UUID | None = None
    created_by_name: str | None = None
    usage_count: int
    approval_status: ApprovalStatus | None = None
    current_approval_level: int | None = None
    approvals: list[TemplateApprovalRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ExtractVariablesRequest(BaseModel):
    """提取变量请求体。"""

    content: str = Field(..., min_length=1, description="Jinja2 模板内容")


class ExtractedVariable(BaseModel):
    """提取的变量信息。"""

    name: str = Field(..., description="变量名")
    label: str = Field(..., description="推荐显示名称")
    param_type: ParamType = Field(..., description="推断的参数类型")
    required: bool = Field(default=True, description="是否必填（默认必填）")


class ExtractVariablesResponse(BaseModel):
    """提取变量响应体。"""

    variables: list[ExtractedVariable] = Field(default_factory=list, description="提取的变量列表")
    raw_names: list[str] = Field(default_factory=list, description="原始变量名列表")


class ParamTypeInfo(BaseModel):
    """参数类型信息。"""

    value: str = Field(..., description="类型值")
    label: str = Field(..., description="显示名称")
    description: str = Field(..., description="类型说明")
    has_options: bool = Field(default=False, description="是否支持选项列表")
    has_range: bool = Field(default=False, description="是否支持范围约束")
    has_pattern: bool = Field(default=False, description="是否支持正则校验")


class ParamTypeListResponse(BaseModel):
    """参数类型列表响应体。"""

    types: list[ParamTypeInfo] = Field(..., description="参数类型列表")


class TemplateExample(BaseModel):
    """模板示例（用于前端展示）。"""

    id: str = Field(..., description="示例模板标识")
    name: str = Field(..., description="示例名称")
    description: str | None = Field(default=None, description="示例描述")
    template_type: TemplateType = Field(default=TemplateType.CUSTOM, description="模板类型")
    content: str = Field(..., description="模板内容(Jinja2)")
    parameters: list[TemplateParameterCreate] = Field(default_factory=list, description="示例参数列表")


class TemplateExampleListResponse(BaseModel):
    """模板示例列表响应体。"""

    examples: list[TemplateExample] = Field(default_factory=list, description="模板示例列表")
