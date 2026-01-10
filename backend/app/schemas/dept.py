"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dept.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils.validators import validate_phone_number


class DeptBase(BaseModel):
    """部门基础模型。"""

    name: str = Field(..., min_length=1, max_length=100, description="部门名称")
    code: str = Field(..., min_length=1, max_length=50, description="部门编码")
    parent_id: UUID | None = Field(default=None, description="父部门ID")
    sort: int = Field(default=0, ge=0, description="排序")
    leader: str | None = Field(default=None, max_length=50, description="负责人")
    phone: str | None = Field(default=None, max_length=20, description="联系电话")
    email: EmailStr | None = Field(default=None, description="联系邮箱")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """验证手机号格式。"""
        return validate_phone_number(v)


class DeptCreate(DeptBase):
    """创建部门请求体。"""

    pass


class DeptUpdate(BaseModel):
    """更新部门请求体。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="部门名称")
    code: str | None = Field(default=None, min_length=1, max_length=50, description="部门编码")
    parent_id: UUID | None = Field(default=None, description="父部门ID")
    sort: int | None = Field(default=None, ge=0, description="排序")
    leader: str | None = Field(default=None, max_length=50, description="负责人")
    phone: str | None = Field(default=None, max_length=20, description="联系电话")
    email: EmailStr | None = Field(default=None, description="联系邮箱")
    is_active: bool | None = Field(default=None, description="是否启用")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """验证手机号格式。"""
        return validate_phone_number(v)


class DeptSimpleResponse(BaseModel):
    """部门简要响应模型（用于关联显示，不包含嵌套关系）。"""

    id: UUID
    name: str
    code: str
    parent_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class DeptResponse(BaseModel):
    """部门响应模型（完整，包含子部门）。"""

    id: UUID
    name: str
    code: str
    parent_id: UUID | None = None
    sort: int
    leader: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    children: list["DeptResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# 前向引用解析
DeptResponse.model_rebuild()
