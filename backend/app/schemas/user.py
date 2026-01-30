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
    """用户基础 Schema。

    用户的基础字段定义，用于创建和更新用户。

    Attributes:
        username (str): 用户名。
        email (EmailStr | None): 邮箱。
        phone (str): 手机号。
        nickname (str | None): 昵称。
        gender (str | None): 性别。
        is_active (bool): 是否激活，默认 True。
        is_superuser (bool): 是否为超级管理员，默认 False。
        dept_id (UUID | None): 所属部门 ID。
    """

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
        """验证手机号格式。

        Args:
            v (str): 手机号字符串。

        Returns:
            str: 验证后的手机号。

        Raises:
            ValueError: 当手机号格式无效时。
        """
        result = validate_phone_number(v, required=True)
        # required=True 保证返回非 None
        assert result is not None
        return result


class UserCreate(UserBase):
    """创建用户请求 Schema。

    用于创建新用户的请求体，包含密码字段。

    Attributes:
        password (str): 密码（明文，存储时加密）。
    """

    password: str = Field(..., description="密码")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度。

        Args:
            v (str): 密码字符串。

        Returns:
            str: 验证后的密码。

        Raises:
            ValueError: 当密码强度不符合要求时。
        """
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    """更新用户请求 Schema。

    用于更新用户信息的请求体，所有字段可选。

    Attributes:
        username (str | None): 用户名。
        email (EmailStr | None): 邮箱。
        phone (str | None): 手机号。
        nickname (str | None): 昵称。
        gender (str | None): 性别。
        is_active (bool | None): 是否激活。
        is_superuser (bool | None): 是否为超级管理员。
        dept_id (UUID | None): 所属部门 ID。
    """

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
        """验证手机号格式。

        Args:
            v (str | None): 手机号字符串。

        Returns:
            str | None: 验证后的手机号，如果为 None 则返回 None。

        Raises:
            ValueError: 当手机号格式无效时。
        """
        return validate_phone_number(v)


class UserMeUpdate(BaseModel):
    """更新当前用户信息请求 Schema（不允许修改 username）。

    用于用户更新自己信息的请求体，不允许修改用户名。

    Attributes:
        email (EmailStr | None): 邮箱。
        phone (str | None): 手机号。
        nickname (str | None): 昵称。
        gender (str | None): 性别。
    """

    email: EmailStr | None = None
    phone: str | None = None
    nickname: str | None = None
    gender: str | None = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def forbid_username_update(cls, data):
        """禁止修改用户名。

        Args:
            data: 输入数据。

        Returns:
            Any: 验证后的数据。

        Raises:
            ValueError: 当尝试修改用户名时。
        """
        if isinstance(data, dict) and data.get("username") is not None:
            raise ValueError("用户名不允许修改")
        return data

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


class UserResponse(UserBase, TimestampSchema):
    """用户响应 Schema。

    用于返回用户信息的响应体，包含用户基本信息和时间戳。

    Attributes:
        id (UUID): 用户 ID。
        is_deleted (bool): 是否删除，默认 False。
        dept_name (str | None): 所属部门名称。
    """

    id: UUID
    is_deleted: bool = Field(False, description="是否删除")
    dept_name: str | None = Field(default=None, description="所属部门名称")

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    """用户修改密码请求 Schema。

    用于用户修改自己密码的请求体。

    Attributes:
        old_password (str): 旧密码。
        new_password (str): 新密码。
    """

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """验证新密码强度。

        Args:
            v (str): 新密码字符串。

        Returns:
            str: 验证后的密码。

        Raises:
            ValueError: 当密码强度不符合要求时。
        """
        return validate_password_strength(v)


class ResetPasswordRequest(BaseModel):
    """管理员重置用户密码请求 Schema。

    用于管理员重置用户密码的请求体。

    Attributes:
        new_password (str): 新密码。
    """

    new_password: str = Field(..., description="新密码")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """验证新密码强度。

        Args:
            v (str): 新密码字符串。

        Returns:
            str: 验证后的密码。

        Raises:
            ValueError: 当密码强度不符合要求时。
        """
        return validate_password_strength(v)


class UserRolesUpdateRequest(BaseModel):
    """用户角色绑定请求 Schema（全量覆盖，幂等）。

    用于更新用户角色绑定的请求体，采用全量覆盖方式。

    Attributes:
        role_ids (list[UUID]): 角色 ID 列表。
    """

    role_ids: list[UUID] = Field(default_factory=list, description="角色ID列表")
