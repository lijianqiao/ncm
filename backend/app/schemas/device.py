"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: device.py
@DateTime: 2026-01-09 19:00:00
@Docs: 设备 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AuthType, DeviceGroup, DeviceStatus, DeviceVendor
from app.schemas.dept import DeptSimpleResponse


class DeviceBase(BaseModel):
    """设备基础模型。"""

    name: str = Field(..., min_length=1, max_length=100, description="设备名称/主机名")
    ip_address: str = Field(..., min_length=7, max_length=45, description="IP 地址")
    vendor: DeviceVendor = Field(default=DeviceVendor.H3C, description="厂商")
    model: str | None = Field(default=None, max_length=100, description="设备型号")
    platform: str | None = Field(default=None, max_length=50, description="平台类型")
    location: str | None = Field(default=None, max_length=200, description="物理位置")
    description: str | None = Field(default=None, description="设备描述")
    ssh_port: int = Field(default=22, ge=1, le=65535, description="SSH 端口")
    auth_type: AuthType = Field(default=AuthType.OTP_SEED, description="认证类型")
    dept_id: UUID | None = Field(default=None, description="所属部门ID")
    device_group: DeviceGroup = Field(default=DeviceGroup.ACCESS, description="设备分组")
    status: DeviceStatus = Field(default=DeviceStatus.IN_USE, description="设备状态")

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """验证 IP 地址格式。"""
        import ipaddress

        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"无效的 IP 地址格式: {v}") from e
        return v


class DeviceCreate(DeviceBase):
    """创建设备请求体。"""

    # 仅 static 类型需要提供用户名和密码
    username: str | None = Field(default=None, max_length=100, description="SSH 用户名(仅 static 类型)")
    password: str | None = Field(default=None, description="SSH 密码(仅 static 类型，明文，存储时加密)")

    # 可选扩展字段
    serial_number: str | None = Field(default=None, max_length=100, description="序列号")
    os_version: str | None = Field(default=None, max_length=100, description="操作系统版本")
    stock_in_at: datetime | None = Field(default=None, description="入库时间")
    assigned_to: str | None = Field(default=None, max_length=100, description="领用人")


class DeviceUpdate(BaseModel):
    """更新设备请求体（所有字段可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="设备名称")
    ip_address: str | None = Field(default=None, min_length=7, max_length=45, description="IP 地址")
    vendor: DeviceVendor | None = Field(default=None, description="厂商")
    model: str | None = Field(default=None, max_length=100, description="设备型号")
    platform: str | None = Field(default=None, max_length=50, description="平台类型")
    location: str | None = Field(default=None, max_length=200, description="物理位置")
    description: str | None = Field(default=None, description="设备描述")
    ssh_port: int | None = Field(default=None, ge=1, le=65535, description="SSH 端口")
    auth_type: AuthType | None = Field(default=None, description="认证类型")
    username: str | None = Field(default=None, max_length=100, description="SSH 用户名")
    password: str | None = Field(default=None, description="SSH 密码(明文，存储时加密)")
    dept_id: UUID | None = Field(default=None, description="所属部门ID")
    device_group: DeviceGroup | None = Field(default=None, description="设备分组")
    status: DeviceStatus | None = Field(default=None, description="设备状态")
    serial_number: str | None = Field(default=None, max_length=100, description="序列号")
    os_version: str | None = Field(default=None, max_length=100, description="操作系统版本")
    stock_in_at: datetime | None = Field(default=None, description="入库时间")
    assigned_to: str | None = Field(default=None, max_length=100, description="领用人")
    retired_at: datetime | None = Field(default=None, description="报废时间")

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        """验证 IP 地址格式。"""
        if v is None:
            return v
        import ipaddress

        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"无效的 IP 地址格式: {v}") from e
        return v


class DeviceResponse(BaseModel):
    """设备响应模型。"""

    id: UUID
    name: str
    ip_address: str
    vendor: str
    model: str | None = None
    platform: str | None = None
    location: str | None = None
    description: str | None = None
    ssh_port: int
    auth_type: str
    dept_id: UUID | None = None
    device_group: str
    status: str
    serial_number: str | None = None
    os_version: str | None = None
    stock_in_at: datetime | None = None
    assigned_to: str | None = None
    retired_at: datetime | None = None
    last_backup_at: datetime | None = None
    last_online_at: datetime | None = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    # 关联部门（使用简要响应，避免嵌套加载 children 导致 MissingGreenlet）
    dept: DeptSimpleResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class DeviceListQuery(BaseModel):
    """设备列表查询参数。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    keyword: str | None = Field(default=None, max_length=100, description="搜索关键词(名称/IP)")
    vendor: DeviceVendor | None = Field(default=None, description="厂商筛选")
    status: DeviceStatus | None = Field(default=None, description="状态筛选")
    device_group: DeviceGroup | None = Field(default=None, description="设备分组筛选")
    dept_id: UUID | None = Field(default=None, description="部门筛选")


class DeviceBatchCreate(BaseModel):
    """批量创建设备请求体。"""

    devices: list[DeviceCreate] = Field(..., min_length=1, max_length=500, description="设备列表")


class DeviceBatchDeleteRequest(BaseModel):
    """批量删除设备请求体。"""

    ids: list[UUID] = Field(..., min_length=1, max_length=100, description="设备ID列表")


class DeviceBatchResult(BaseModel):
    """批量操作结果。"""

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_items: list[dict] = Field(default_factory=list, description="失败项详情")


class DeviceStatusTransitionRequest(BaseModel):
    """设备状态流转请求体。"""

    to_status: DeviceStatus = Field(..., description="目标状态")
    reason: str | None = Field(default=None, max_length=500, description="流转原因(可选)")


class DeviceStatusBatchTransitionRequest(BaseModel):
    """批量状态流转请求体。"""

    ids: list[UUID] = Field(..., min_length=1, max_length=500, description="设备ID列表")
    to_status: DeviceStatus = Field(..., description="目标状态")
    reason: str | None = Field(default=None, max_length=500, description="流转原因(可选)")


class DeviceLifecycleStatsResponse(BaseModel):
    """设备生命周期统计响应。"""

    by_status: dict[str, int] = Field(default_factory=dict, description="按状态统计")
    by_vendor: dict[str, int] = Field(default_factory=dict, description="按厂商统计")
    by_dept: dict[str, int] = Field(default_factory=dict, description="按部门统计（dept_id 字符串）")
