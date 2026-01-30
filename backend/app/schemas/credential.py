"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credential.py
@DateTime: 2026-01-09 17:00:00
@Docs: 设备凭据相关 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AuthType, DeviceGroup


class DeviceCredential(BaseModel):
    """设备连接凭据 Schema（用于 SSH 登录）。

    根据认证类型，password 字段的含义不同：
    - static: 静态密码明文
    - otp_seed: PyOTP 自动生成的 TOTP 验证码
    - otp_manual: 用户手动输入的 OTP 验证码（从缓存获取）

    Attributes:
        username (str): SSH 用户名。
        password (str): 密码或 OTP 验证码。
        auth_type (AuthType): 认证类型。
    """

    username: str = Field(..., description="SSH 用户名")
    password: str = Field(..., description="密码或 OTP 验证码")
    auth_type: AuthType = Field(..., description="认证类型")

    model_config = ConfigDict(from_attributes=True)


def _extract_value(v):
    """从复杂结构中提取值（支持字典、列表等前端传入格式）。

    Args:
        v: 输入值，可能是字典、列表或简单值。

    Returns:
        Any: 提取后的值。
    """
    if isinstance(v, dict):
        for key in ("value", "id", "dept_id", "key", "label"):
            if key in v:
                return _extract_value(v[key])
        return v
    if isinstance(v, list) and len(v) == 1:
        return _extract_value(v[0])
    return v


# 设备分组中文映射
_DEVICE_GROUP_MAPPING: dict[str, str] = {
    "核心层": "core",
    "汇聚层": "distribution",
    "接入层": "access",
    "核心": "core",
    "汇聚": "distribution",
    "接入": "access",
}


class OTPRequestBase(BaseModel):
    """OTP 请求基类 Schema，统一验证逻辑。

    Attributes:
        dept_id (UUID): 部门 ID。
        device_group (DeviceGroup): 设备分组。
        otp_code (str): OTP 验证码，长度 6-8 位。
    """

    dept_id: UUID = Field(..., description="部门ID")
    device_group: DeviceGroup = Field(..., description="设备分组")
    otp_code: str = Field(..., min_length=6, max_length=8, description="OTP 验证码")

    @field_validator("dept_id", mode="before")
    @classmethod
    def _normalize_dept_id(cls, v):
        """从复杂结构中提取部门 ID。

        Args:
            v: 输入值。

        Returns:
            Any: 提取后的部门 ID。
        """
        return _extract_value(v)

    @field_validator("device_group", mode="before")
    @classmethod
    def _normalize_device_group(cls, v):
        """规范化设备分组（支持中文转换）。

        Args:
            v: 输入值。

        Returns:
            str: 规范化后的设备分组值。
        """
        v = _extract_value(v)
        if isinstance(v, str):
            value = v.strip().lower()
            return _DEVICE_GROUP_MAPPING.get(value, value)
        return v


class OTPCacheRequest(OTPRequestBase):
    """OTP 缓存请求 Schema（用户手动输入 OTP 时）。

    用于用户手动输入 OTP 并缓存的请求体。
    """

    pass


class OTPCacheResponse(BaseModel):
    """OTP 缓存响应 Schema。

    用于 OTP 缓存操作的响应体。

    Attributes:
        success (bool): 是否成功。
        message (str): 消息。
        expires_in (int): 剩余有效期（秒）。
    """

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    expires_in: int = Field(..., description="剩余有效期（秒）")


class OTPVerifyRequest(OTPRequestBase):
    """OTP 验证请求 Schema（验证 + 缓存）。

    用于验证 OTP 并缓存的请求体。
    """

    pass


class OTPVerifyResponse(BaseModel):
    """OTP 验证响应 Schema。

    用于 OTP 验证操作的响应体。

    Attributes:
        verified (bool): 验证是否成功。
        message (str): 消息。
        expires_in (int): OTP 缓存剩余有效期（秒），默认 0。
        device_tested (str | None): 测试连接的设备名称。
    """

    verified: bool = Field(..., description="验证是否成功")
    message: str = Field(..., description="消息")
    expires_in: int = Field(default=0, description="OTP 缓存剩余有效期（秒）")
    device_tested: str | None = Field(default=None, description="测试连接的设备名称")


class DeviceGroupCredentialCreate(BaseModel):
    """创建设备分组凭据请求 Schema。

    用于创建新设备分组凭据的请求体。

    Attributes:
        dept_id (UUID): 部门 ID。
        device_group (DeviceGroup): 设备分组。
        username (str): SSH 账号。
        otp_seed (str | None): OTP 种子（明文，存储时加密）。
        auth_type (AuthType): 认证类型，默认 OTP_SEED。
        description (str | None): 凭据描述。
    """

    dept_id: UUID = Field(..., description="部门ID")
    device_group: DeviceGroup = Field(..., description="设备分组")
    username: str = Field(..., min_length=1, max_length=100, description="SSH 账号")
    otp_seed: str | None = Field(None, description="OTP 种子（明文，存储时加密）")
    auth_type: AuthType = Field(AuthType.OTP_SEED, description="认证类型")
    description: str | None = Field(None, max_length=200, description="凭据描述")


class DeviceGroupCredentialUpdate(BaseModel):
    """更新设备分组凭据请求 Schema。

    用于更新设备分组凭据信息的请求体，所有字段可选。

    Attributes:
        username (str | None): SSH 账号。
        otp_seed (str | None): OTP 种子（明文，存储时加密）。
        auth_type (AuthType | None): 认证类型。
        description (str | None): 凭据描述。
    """

    username: str | None = Field(None, min_length=1, max_length=100, description="SSH 账号")
    otp_seed: str | None = Field(None, description="OTP 种子（明文，存储时加密）")
    auth_type: AuthType | None = Field(None, description="认证类型")
    description: str | None = Field(None, max_length=200, description="凭据描述")


class DeviceGroupCredentialResponse(BaseModel):
    """设备分组凭据响应 Schema。

    用于返回设备分组凭据信息的响应体。

    Attributes:
        id (UUID): 凭据 ID。
        dept_id (UUID): 部门 ID。
        dept_name (str | None): 部门名称。
        device_group (DeviceGroup): 设备分组。
        username (str): SSH 账号。
        auth_type (AuthType): 认证类型。
        description (str | None): 凭据描述。
        has_otp_seed (bool): 是否配置了 OTP 种子。
        created_at (datetime): 创建时间。
        updated_at (datetime | None): 更新时间。
    """

    id: UUID = Field(..., description="凭据ID")
    dept_id: UUID = Field(..., description="部门ID")
    dept_name: str | None = Field(None, description="部门名称")
    device_group: DeviceGroup = Field(..., description="设备分组")
    username: str = Field(..., description="SSH 账号")
    auth_type: AuthType = Field(..., description="认证类型")
    description: str | None = Field(None, description="凭据描述")
    has_otp_seed: bool = Field(..., description="是否配置了 OTP 种子")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CredentialBatchRequest(BaseModel):
    """凭据批量操作请求 Schema。

    用于批量操作（删除等）凭据的请求体。

    Attributes:
        ids (list[UUID]): 凭据 ID 列表，至少包含 1 个。
    """

    ids: list[UUID] = Field(..., min_length=1, description="凭据ID列表")


class CredentialBatchResult(BaseModel):
    """凭据批量操作结果 Schema。

    用于批量操作（删除等）凭据的响应 Schema。

    Attributes:
        success_count (int): 成功数量。
        failed_count (int): 失败数量。
        failed_ids (list[UUID]): 失败的 ID 列表。
    """

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="失败的ID列表")
