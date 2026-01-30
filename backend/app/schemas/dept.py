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
    """部门基础 Schema。

    部门的基础字段定义，用于创建和更新部门。

    Attributes:
        name (str): 部门名称。
        code (str): 部门编码。
        parent_id (UUID | None): 父部门 ID。
        sort (int): 排序，默认 0。
        leader (str | None): 负责人。
        phone (str | None): 联系电话。
        email (EmailStr | None): 联系邮箱。
    """

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
        """验证手机号格式。

        Args:
            v (str | None): 手机号字符串。

        Returns:
            str | None: 验证后的手机号，如果为 None 则返回 None。

        Raises:
            ValueError: 当手机号格式无效时。
        """
        return validate_phone_number(v)


class DeptCreate(DeptBase):
    """创建部门请求 Schema。

    用于创建新部门的请求体，继承自 DeptBase。
    """

    pass


class DeptUpdate(BaseModel):
    """更新部门请求 Schema。

    用于更新部门信息的请求体，所有字段可选。

    Attributes:
        name (str | None): 部门名称。
        code (str | None): 部门编码。
        parent_id (UUID | None): 父部门 ID。
        sort (int | None): 排序。
        leader (str | None): 负责人。
        phone (str | None): 联系电话。
        email (EmailStr | None): 联系邮箱。
        is_active (bool | None): 是否启用。
    """

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
        """验证手机号格式。

        Args:
            v (str | None): 手机号字符串。

        Returns:
            str | None: 验证后的手机号，如果为 None 则返回 None。

        Raises:
            ValueError: 当手机号格式无效时。
        """
        return validate_phone_number(v)


class DeptSimpleResponse(BaseModel):
    """部门简要响应 Schema（用于关联显示，不包含嵌套关系）。

    用于关联显示的部门简要信息，不包含子部门等嵌套关系。

    Attributes:
        id (UUID): 部门 ID。
        name (str): 部门名称。
        code (str): 部门编码。
        parent_id (UUID | None): 父部门 ID。
    """

    id: UUID
    name: str
    code: str
    parent_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class DeptResponse(BaseModel):
    """部门响应 Schema（完整，包含子部门）。

    用于返回部门完整信息的响应体，包含子部门列表。

    Attributes:
        id (UUID): 部门 ID。
        name (str): 部门名称。
        code (str): 部门编码。
        parent_id (UUID | None): 父部门 ID。
        sort (int): 排序。
        leader (str | None): 负责人。
        phone (str | None): 联系电话。
        email (str | None): 联系邮箱。
        is_active (bool): 是否激活。
        is_deleted (bool): 是否删除。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
        children (list[DeptResponse]): 子部门列表。
    """

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
