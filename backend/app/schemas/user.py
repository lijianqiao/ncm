"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: user.py
@DateTime: 2025-12-30 14:45:00
@Docs: 用户 User 相关 Schema 定义。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.common import TimestampSchema
from app.utils.validators import validate_password_strength, validate_phone_number


class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: EmailStr | None = Field(None, description="邮箱")
    phone: str = Field(..., description="手机号")
    nickname: str | None = Field(None, description="昵称")
    gender: str | None = Field(None, description="性别")
    is_active: bool = Field(True, description="是否激活")
    is_superuser: bool = Field(False, description="是否为超级管理员")
    dept_id: UUID | None = Field(None, description="所属部门ID")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """验证手机号格式。"""
        result = validate_phone_number(v, required=True)
        # required=True 保证返回非 None
        assert result is not None
        return result


class UserCreate(UserBase):
    password: str = Field(..., description="密码")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    nickname: str | None = None
    gender: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    dept_id: UUID | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """验证手机号格式。"""
        return validate_phone_number(v)


class UserMeUpdate(BaseModel):
    """更新当前用户信息请求（不允许修改 username）。"""

    email: EmailStr | None = None
    phone: str | None = None
    nickname: str | None = None
    gender: str | None = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def forbid_username_update(cls, data):
        if isinstance(data, dict) and data.get("username") is not None:
            raise ValueError("用户名不允许修改")
        return data

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """验证手机号格式。"""
        return validate_phone_number(v)


class UserResponse(UserBase, TimestampSchema):
    id: UUID
    is_deleted: bool = Field(False, description="是否删除")
    dept_name: str | None = Field(default=None, description="所属部门名称")

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    """
    用户修改密码请求。
    """

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ResetPasswordRequest(BaseModel):
    """
    管理员重置用户密码请求。
    """

    new_password: str = Field(..., description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserRolesUpdateRequest(BaseModel):
    """用户角色绑定请求（全量覆盖，幂等）。"""

    role_ids: list[UUID] = Field(default_factory=list, description="角色ID列表")
