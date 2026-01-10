"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credential.py
@DateTime: 2026-01-09 17:00:00
@Docs: 设备凭据相关 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AuthType, DeviceGroup


class DeviceCredential(BaseModel):
    """
    设备连接凭据（用于 SSH 登录）。

    根据认证类型，password 字段的含义不同：
    - static: 静态密码明文
    - otp_seed: PyOTP 自动生成的 TOTP 验证码
    - otp_manual: 用户手动输入的 OTP 验证码（从缓存获取）
    """

    username: str = Field(..., description="SSH 用户名")
    password: str = Field(..., description="密码或 OTP 验证码")
    auth_type: AuthType = Field(..., description="认证类型")

    model_config = ConfigDict(from_attributes=True)


class OTPCacheRequest(BaseModel):
    """OTP 缓存请求（用户手动输入 OTP 时）。"""

    dept_id: UUID = Field(..., description="部门ID")
    device_group: DeviceGroup = Field(..., description="设备分组")
    otp_code: str = Field(..., min_length=6, max_length=8, description="OTP 验证码")


class OTPCacheResponse(BaseModel):
    """OTP 缓存响应。"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    expires_in: int = Field(..., description="剩余有效期（秒）")


class DeviceGroupCredentialCreate(BaseModel):
    """创建设备分组凭据请求。"""

    dept_id: UUID = Field(..., description="部门ID")
    device_group: DeviceGroup = Field(..., description="设备分组")
    username: str = Field(..., min_length=1, max_length=100, description="SSH 账号")
    otp_seed: str | None = Field(None, description="OTP 种子（明文，存储时加密）")
    auth_type: AuthType = Field(AuthType.OTP_SEED, description="认证类型")
    description: str | None = Field(None, max_length=200, description="凭据描述")


class DeviceGroupCredentialUpdate(BaseModel):
    """更新设备分组凭据请求。"""

    username: str | None = Field(None, min_length=1, max_length=100, description="SSH 账号")
    otp_seed: str | None = Field(None, description="OTP 种子（明文，存储时加密）")
    auth_type: AuthType | None = Field(None, description="认证类型")
    description: str | None = Field(None, max_length=200, description="凭据描述")


class DeviceGroupCredentialResponse(BaseModel):
    """设备分组凭据响应。"""

    id: UUID = Field(..., description="凭据ID")
    dept_id: UUID = Field(..., description="部门ID")
    dept_name: str | None = Field(None, description="部门名称")
    device_group: str = Field(..., description="设备分组")
    username: str = Field(..., description="SSH 账号")
    auth_type: str = Field(..., description="认证类型")
    description: str | None = Field(None, description="凭据描述")
    has_otp_seed: bool = Field(..., description="是否配置了 OTP 种子")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)
