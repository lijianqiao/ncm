"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: collect.py
@DateTime: 2026-01-09 22:00:00
@Docs: ARP/MAC 采集 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.utils.validators import validate_ip_address, validate_mac_address

# ===== ARP 表相关 =====


class ARPEntry(BaseModel):
    """ARP 表条目。"""

    ip_address: str = Field(..., description="IP 地址")
    mac_address: str = Field(..., description="MAC 地址")
    vlan_id: str | None = Field(default=None, description="VLAN ID")
    interface: str | None = Field(default=None, description="接口名称")
    age: str | None = Field(default=None, description="老化时间")
    entry_type: str | None = Field(default=None, description="条目类型 (Dynamic/Static)")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """验证 IP 地址格式。"""
        return validate_ip_address(v)

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        """验证 MAC 地址格式。"""
        return validate_mac_address(v)


class ARPTableResponse(BaseModel):
    """ARP 表响应。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    entries: list[ARPEntry] = Field(default_factory=list, description="ARP 条目列表")
    total: int = Field(default=0, description="总条目数")
    cached_at: datetime | None = Field(default=None, description="缓存时间")


# ===== MAC 表相关 =====


class MACEntry(BaseModel):
    """MAC 地址表条目。"""

    mac_address: str = Field(..., description="MAC 地址")
    vlan_id: str | None = Field(default=None, description="VLAN ID")
    interface: str | None = Field(default=None, description="接口名称")
    entry_type: str | None = Field(default=None, description="条目类型 (Learned/Config/Static)")
    state: str | None = Field(default=None, description="状态")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        """验证 MAC 地址格式。"""
        return validate_mac_address(v)


class MACTableResponse(BaseModel):
    """MAC 地址表响应。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    entries: list[MACEntry] = Field(default_factory=list, description="MAC 条目列表")
    total: int = Field(default=0, description="总条目数")
    cached_at: datetime | None = Field(default=None, description="缓存时间")


# ===== 采集请求 =====


class CollectDeviceRequest(BaseModel):
    """采集单设备请求。"""

    collect_arp: bool = Field(default=True, description="是否采集 ARP 表")
    collect_mac: bool = Field(default=True, description="是否采集 MAC 表")
    otp_code: str | None = Field(default=None, description="OTP 验证码（如果设备需要）")


class CollectBatchRequest(BaseModel):
    """批量采集请求。"""

    device_ids: list[UUID] = Field(..., min_length=1, description="设备ID列表")
    collect_arp: bool = Field(default=True, description="是否采集 ARP 表")
    collect_mac: bool = Field(default=True, description="是否采集 MAC 表")
    otp_code: str | None = Field(default=None, description="OTP 验证码（如果设备需要）")


# ===== 采集结果 =====


class DeviceCollectResult(BaseModel):
    """单设备采集结果。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    success: bool = Field(default=False, description="是否成功")
    arp_count: int = Field(default=0, description="ARP 条目数")
    mac_count: int = Field(default=0, description="MAC 条目数")
    error_message: str | None = Field(default=None, description="错误信息")
    duration_ms: int | None = Field(default=None, description="耗时（毫秒）")


class CollectResult(BaseModel):
    """采集任务结果。"""

    task_id: str | None = Field(default=None, description="Celery 任务ID（异步任务时返回）")
    total_devices: int = Field(default=0, description="总设备数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
    results: list[DeviceCollectResult] = Field(default_factory=list, description="各设备采集结果")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")


class CollectTaskStatus(BaseModel):
    """采集任务状态（用于查询异步任务）。"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态 (PENDING/STARTED/SUCCESS/FAILURE)")
    progress: int = Field(default=0, description="进度百分比")
    result: CollectResult | None = Field(default=None, description="任务结果（完成时）")
    error: str | None = Field(default=None, description="错误信息（失败时）")


# ===== IP/MAC 定位相关 =====


class LocateMatch(BaseModel):
    """单条定位匹配结果。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    device_ip: str | None = Field(default=None, description="设备管理IP")
    interface: str | None = Field(default=None, description="接口/端口")
    vlan_id: str | None = Field(default=None, description="VLAN ID")
    ip_address: str | None = Field(default=None, description="IP 地址（MAC 查询时返回）")
    mac_address: str | None = Field(default=None, description="MAC 地址（IP 查询时返回）")
    entry_type: str | None = Field(default=None, description="条目类型")
    cached_at: datetime | None = Field(default=None, description="数据缓存时间")


class LocateResponse(BaseModel):
    """定位查询响应。"""

    query: str = Field(..., description="查询的 IP 或 MAC 地址")
    query_type: str = Field(..., description="查询类型 (ip/mac)")
    matches: list[LocateMatch] = Field(default_factory=list, description="匹配结果列表")
    total: int = Field(default=0, description="匹配总数")
    searched_devices: int = Field(default=0, description="搜索的设备数")
    search_time_ms: int = Field(default=0, description="搜索耗时（毫秒）")
