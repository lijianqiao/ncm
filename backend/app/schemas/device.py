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
from app.schemas.common import PaginatedQuery
from app.schemas.dept import DeptSimpleResponse
from app.utils.validators import validate_ip_address


class DeviceBase(BaseModel):
    """设备基础 Schema。

    设备的基础字段定义，用于创建和更新设备。

    Attributes:
        name (str): 设备名称/主机名。
        ip_address (str): IP 地址。
        vendor (DeviceVendor): 厂商，默认 H3C。
        model (str | None): 设备型号。
        platform (str | None): 平台类型。
        location (str | None): 物理位置。
        description (str | None): 设备描述。
        ssh_port (int): SSH 端口，默认 22。
        auth_type (AuthType): 认证类型，默认 OTP_SEED。
        dept_id (UUID | None): 所属部门 ID。
        device_group (DeviceGroup): 设备分组，默认 ACCESS。
        status (DeviceStatus): 设备状态，默认 IN_USE。
    """

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
        """验证 IP 地址格式。

        Args:
            v (str): IP 地址字符串。

        Returns:
            str: 验证后的 IP 地址。

        Raises:
            ValueError: 当 IP 地址格式无效时。
        """
        return validate_ip_address(v)


class DeviceCreate(DeviceBase):
    """创建设备请求 Schema。

    用于创建新设备的请求体，包含静态认证的凭据字段和扩展信息。

    Attributes:
        username (str | None): SSH 用户名（仅 static 类型）。
        password (str | None): SSH 密码（仅 static 类型，明文，存储时加密）。
        serial_number (str | None): 序列号。
        os_version (str | None): 操作系统版本。
        stock_in_at (datetime | None): 入库时间。
        assigned_to (str | None): 领用人。
    """

    # 仅 static 类型需要提供用户名和密码
    username: str | None = Field(default=None, max_length=100, description="SSH 用户名(仅 static 类型)")
    password: str | None = Field(default=None, description="SSH 密码(仅 static 类型，明文，存储时加密)")

    # 可选扩展字段
    serial_number: str | None = Field(default=None, max_length=100, description="序列号")
    os_version: str | None = Field(default=None, max_length=100, description="操作系统版本")
    stock_in_at: datetime | None = Field(default=None, description="入库时间")
    assigned_to: str | None = Field(default=None, max_length=100, description="领用人")


class DeviceUpdate(BaseModel):
    """更新设备请求 Schema（所有字段可选）。

    用于更新设备信息的请求体，所有字段可选。

    Attributes:
        name (str | None): 设备名称。
        ip_address (str | None): IP 地址。
        vendor (DeviceVendor | None): 厂商。
        model (str | None): 设备型号。
        platform (str | None): 平台类型。
        location (str | None): 物理位置。
        description (str | None): 设备描述。
        ssh_port (int | None): SSH 端口。
        auth_type (AuthType | None): 认证类型。
        username (str | None): SSH 用户名。
        password (str | None): SSH 密码（明文，存储时加密）。
        dept_id (UUID | None): 所属部门 ID。
        device_group (DeviceGroup | None): 设备分组。
        status (DeviceStatus | None): 设备状态。
        serial_number (str | None): 序列号。
        os_version (str | None): 操作系统版本。
        stock_in_at (datetime | None): 入库时间。
        assigned_to (str | None): 领用人。
        retired_at (datetime | None): 报废时间。
    """

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
        """验证 IP 地址格式。

        Args:
            v (str | None): IP 地址字符串。

        Returns:
            str | None: 验证后的 IP 地址，如果为 None 则返回 None。

        Raises:
            ValueError: 当 IP 地址格式无效时。
        """
        if v is None:
            return v
        return validate_ip_address(v)


class DeviceResponse(BaseModel):
    """设备响应 Schema。

    用于返回设备信息的响应体，包含设备的所有字段和关联信息。

    Attributes:
        id (UUID): 设备 ID。
        name (str): 设备名称。
        ip_address (str): IP 地址。
        vendor (DeviceVendor): 厂商。
        model (str | None): 设备型号。
        platform (str | None): 平台类型。
        location (str | None): 物理位置。
        description (str | None): 设备描述。
        ssh_port (int): SSH 端口。
        auth_type (AuthType): 认证类型。
        dept_id (UUID | None): 所属部门 ID。
        device_group (DeviceGroup): 设备分组。
        status (DeviceStatus): 设备状态。
        serial_number (str | None): 序列号。
        os_version (str | None): 操作系统版本。
        stock_in_at (datetime | None): 入库时间。
        assigned_to (str | None): 领用人。
        retired_at (datetime | None): 报废时间。
        last_backup_at (datetime | None): 最后备份时间。
        last_online_at (datetime | None): 最后在线时间。
        is_deleted (bool): 是否删除。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
        dept (DeptSimpleResponse | None): 所属部门简要信息。
    """

    id: UUID
    name: str
    ip_address: str
    vendor: DeviceVendor
    model: str | None = None
    platform: str | None = None
    location: str | None = None
    description: str | None = None
    ssh_port: int
    auth_type: AuthType
    dept_id: UUID | None = None
    device_group: DeviceGroup
    status: DeviceStatus
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

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class DeviceListQuery(PaginatedQuery):
    """设备列表查询参数 Schema。

    用于设备列表查询的请求参数，包含分页和筛选条件。

    Attributes:
        keyword (str | None): 搜索关键词（名称/IP）。
        vendor (DeviceVendor | None): 厂商筛选。
        status (DeviceStatus | None): 状态筛选。
        device_group (DeviceGroup | None): 设备分组筛选。
        dept_id (UUID | None): 部门筛选。
    """

    keyword: str | None = Field(default=None, max_length=100, description="搜索关键词(名称/IP)")
    vendor: DeviceVendor | None = Field(default=None, description="厂商筛选")
    status: DeviceStatus | None = Field(default=None, description="状态筛选")
    device_group: DeviceGroup | None = Field(default=None, description="设备分组筛选")
    dept_id: UUID | None = Field(default=None, description="部门筛选")


class DeviceBatchCreate(BaseModel):
    """批量创建设备请求 Schema。

    用于批量创建设备的请求体。

    Attributes:
        devices (list[DeviceCreate]): 设备列表，数量范围 1-500。
    """

    devices: list[DeviceCreate] = Field(..., min_length=1, max_length=500, description="设备列表")


class DeviceBatchDeleteRequest(BaseModel):
    """批量删除设备请求 Schema。

    用于批量删除设备的请求体。

    Attributes:
        ids (list[UUID]): 设备 ID 列表，数量范围 1-100。
    """

    ids: list[UUID] = Field(..., min_length=1, max_length=100, description="设备ID列表")


class DeviceBatchResult(BaseModel):
    """批量操作结果 Schema。

    用于批量操作（创建、删除等）的响应 Schema。

    Attributes:
        success_count (int): 成功数量。
        failed_count (int): 失败数量。
        failed_items (list[dict]): 失败项详情。
    """

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_items: list[dict] = Field(default_factory=list, description="失败项详情")


class DeviceStatusTransitionRequest(BaseModel):
    """设备状态流转请求 Schema。

    用于设备状态流转的请求体。

    Attributes:
        to_status (DeviceStatus): 目标状态。
        reason (str | None): 流转原因（可选）。
    """

    to_status: DeviceStatus = Field(..., description="目标状态")
    reason: str | None = Field(default=None, max_length=500, description="流转原因(可选)")


class DeviceStatusBatchTransitionRequest(BaseModel):
    """批量状态流转请求 Schema。

    用于批量设备状态流转的请求体。

    Attributes:
        ids (list[UUID]): 设备 ID 列表，数量范围 1-500。
        to_status (DeviceStatus): 目标状态。
        reason (str | None): 流转原因（可选）。
    """

    ids: list[UUID] = Field(..., min_length=1, max_length=500, description="设备ID列表")
    to_status: DeviceStatus = Field(..., description="目标状态")
    reason: str | None = Field(default=None, max_length=500, description="流转原因(可选)")


class DeviceLifecycleStatsResponse(BaseModel):
    """设备生命周期统计响应。"""

    by_status: dict[str, int] = Field(default_factory=dict, description="按状态统计")
    by_vendor: dict[str, int] = Field(default_factory=dict, description="按厂商统计")
    by_dept: dict[str, int] = Field(default_factory=dict, description="按部门统计（dept_id 字符串）")


class DeviceStatusCounts(BaseModel):
    """设备状态计数。"""

    stock: int = Field(default=0, description="库存数量")
    running: int = Field(default=0, description="运行中数量")
    maintenance: int = Field(default=0, description="维护中数量")
    retired: int = Field(default=0, description="已退役数量")
    total: int = Field(default=0, description="总数量")


class DeviceListResponse(BaseModel):
    """设备列表响应（含状态统计）。"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    items: list["DeviceResponse"] = Field(default_factory=list, description="数据列表")
    status_counts: DeviceStatusCounts = Field(default_factory=DeviceStatusCounts, description="各状态设备数量")
