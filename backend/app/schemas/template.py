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

from app.core.enums import DeviceType, DeviceVendor, TemplateStatus, TemplateType


class TemplateBase(BaseModel):
    """模板基础字段。"""

    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType = Field(default=TemplateType.CUSTOM, description="模板类型")
    content: str = Field(..., min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] = Field(..., min_length=1, description="适用厂商列表")
    device_type: DeviceType = Field(default=DeviceType.ALL, description="适用设备类型")
    parameters: str | None = Field(default=None, description="参数定义(JSON Schema 字符串)")


class TemplateCreate(TemplateBase):
    """创建模板请求体。"""

    pass


class TemplateUpdate(BaseModel):
    """更新模板请求体（字段均可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    template_type: TemplateType | None = Field(default=None, description="模板类型")
    content: str | None = Field(default=None, min_length=1, description="Jinja2 模板内容")
    vendors: list[DeviceVendor] | None = Field(default=None, min_length=1, description="适用厂商列表")
    device_type: DeviceType | None = Field(default=None, description="适用设备类型")
    parameters: str | None = Field(default=None, description="参数定义(JSON Schema 字符串)")
    status: TemplateStatus | None = Field(default=None, description="模板状态")


class TemplateResponse(BaseModel):
    """模板响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    template_type: str
    content: str
    vendors: list[str]
    device_type: str
    parameters: str | None = None
    version: int
    parent_id: UUID | None = None
    status: str
    creator_id: UUID | None = None
    usage_count: int
    created_at: datetime
    updated_at: datetime


class TemplateListQuery(BaseModel):
    """模板列表查询参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    vendor: DeviceVendor | None = None
    template_type: TemplateType | None = None
    status: TemplateStatus | None = None


class TemplateNewVersionRequest(BaseModel):
    """基于某个模板版本创建新版本。"""

    name: str | None = Field(default=None, description="新版本名称(可选)")
    description: str | None = Field(default=None, description="新版本描述(可选)")


class TemplateSubmitRequest(BaseModel):
    """提交模板审批。"""

    comment: str | None = Field(default=None, description="提交说明(可选)")

