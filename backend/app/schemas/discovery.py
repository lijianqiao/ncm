"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery.py
@DateTime: 2026-01-09 23:10:00
@Docs: 设备发现 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import DiscoveryStatus
from app.utils.validators import validate_ip_address, validate_mac_address

# ===== 扫描请求 =====


class ScanRequest(BaseModel):
    """网络扫描请求。"""

    subnets: list[str] = Field(..., min_length=1, description="待扫描网段列表 (CIDR 格式)")
    scan_type: str = Field(default="auto", description="扫描类型 (auto/nmap/masscan)")
    ports: str | None = Field(default=None, description="扫描端口 (如 22,23,80,443)")
    async_mode: bool = Field(default=True, description="是否异步执行")

    @field_validator("scan_type")
    @classmethod
    def validate_scan_type(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v in {"auto", "nmap", "masscan"}:
            return v
        raise ValueError("scan_type 仅支持 auto/nmap/masscan")


class ScanSubnetRequest(BaseModel):
    """单网段扫描请求。"""

    subnet: str = Field(..., description="网段 (CIDR 格式，如 192.168.1.0/24)")
    scan_type: str = Field(default="auto", description="扫描类型 (auto/nmap/masscan)")
    ports: str | None = Field(default=None, description="扫描端口")

    @field_validator("scan_type")
    @classmethod
    def validate_scan_type(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v in {"auto", "nmap", "masscan"}:
            return v
        raise ValueError("scan_type 仅支持 auto/nmap/masscan")


# ===== 扫描结果 =====


class ScanHost(BaseModel):
    """扫描发现的主机。"""

    ip_address: str = Field(..., description="IP 地址")
    mac_address: str | None = Field(default=None, description="MAC 地址")
    hostname: str | None = Field(default=None, description="主机名")
    vendor: str | None = Field(default=None, description="厂商 (OUI 识别)")
    os_info: str | None = Field(default=None, description="操作系统信息")
    open_ports: dict[int, str] | None = Field(default=None, description="开放端口 {port: service}")
    status: str = Field(default="up", description="主机状态")

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """验证 IP 地址格式。"""
        return validate_ip_address(v)

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str | None) -> str | None:
        """验证 MAC 地址格式。"""
        if v is None:
            return v
        return validate_mac_address(v)


class ScanResult(BaseModel):
    """扫描任务结果。"""

    task_id: str | None = Field(default=None, description="Celery 任务ID")
    subnet: str = Field(..., description="扫描网段")
    scan_type: str = Field(..., description="扫描类型")
    hosts_found: int = Field(default=0, description="发现主机数")
    hosts: list[ScanHost] = Field(default_factory=list, description="发现的主机列表")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    duration_seconds: int | None = Field(default=None, description="耗时(秒)")
    error: str | None = Field(default=None, description="错误信息")


class ScanTaskStatus(BaseModel):
    """扫描任务状态。"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(default=0, description="进度百分比")
    result: ScanResult | None = Field(default=None, description="扫描结果")
    error: str | None = Field(default=None, description="错误信息")


class ScanTaskResponse(BaseModel):
    """扫描任务提交响应。"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(default="pending", description="任务状态")
    message: str = Field(default="扫描任务已提交", description="提示信息")


class AdoptResponse(BaseModel):
    """设备纳管响应。"""

    message: str = Field(default="设备纳管成功", description="操作结果消息")
    device_id: str = Field(..., description="新设备ID")
    device_name: str = Field(..., description="设备名称")


class DeleteResponse(BaseModel):
    """删除操作响应。"""

    message: str = Field(default="删除成功", description="操作结果消息")


# ===== Discovery CRUD =====


class DiscoveryBase(BaseModel):
    """发现记录基础模型。"""

    ip_address: str = Field(..., description="IP 地址")
    mac_address: str | None = Field(default=None, description="MAC 地址")
    vendor: str | None = Field(default=None, description="厂商")
    device_type: str | None = Field(default=None, description="设备类型")
    hostname: str | None = Field(default=None, description="主机名")
    os_info: str | None = Field(default=None, description="操作系统信息")

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """验证 IP 地址格式。"""
        return validate_ip_address(v)

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str | None) -> str | None:
        """验证 MAC 地址格式。"""
        if v is None:
            return v
        return validate_mac_address(v)


class DiscoveryCreate(DiscoveryBase):
    """创建发现记录。"""

    open_ports: dict[int, str] | None = Field(default=None, description="开放端口")
    ssh_banner: str | None = Field(default=None, description="SSH Banner")
    scan_source: str | None = Field(default=None, description="扫描来源")
    scan_task_id: str | None = Field(default=None, description="扫描任务ID")


class DiscoveryUpdate(BaseModel):
    """更新发现记录。"""

    status: DiscoveryStatus | None = Field(default=None, description="状态")
    matched_device_id: UUID | None = Field(default=None, description="匹配的设备ID")
    vendor: str | None = Field(default=None, description="厂商")
    device_type: str | None = Field(default=None, description="设备类型")


class DiscoveryResponse(DiscoveryBase):
    """发现记录响应。"""

    id: UUID
    open_ports: dict | None = None
    ssh_banner: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    offline_days: int
    status: str
    matched_device_id: UUID | None = None
    scan_source: str | None = None
    created_at: datetime
    updated_at: datetime

    # 关联的设备信息（简要）
    matched_device_name: str | None = Field(default=None, description="匹配设备名称")
    matched_device_ip: str | None = Field(default=None, description="匹配设备IP")

    model_config = ConfigDict(from_attributes=True)


class DiscoveryListQuery(BaseModel):
    """发现记录列表查询参数。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: DiscoveryStatus | None = Field(default=None, description="状态筛选")
    keyword: str | None = Field(default=None, description="关键词搜索 (IP/主机名)")
    scan_source: str | None = Field(default=None, description="扫描来源筛选")


# ===== 纳管设备 =====


class AdoptDeviceRequest(BaseModel):
    """纳管设备请求（将发现记录转为正式设备）。"""

    name: str = Field(..., min_length=1, max_length=100, description="设备名称")
    vendor: str = Field(default="other", description="设备厂商")
    device_group: str = Field(default="access", description="设备分组")
    dept_id: UUID | None = Field(default=None, description="所属部门ID")
    username: str | None = Field(default=None, description="SSH 用户名")
    password: str | None = Field(default=None, description="SSH 密码")


# ===== 比对结果 =====


class CMDBCompareResult(BaseModel):
    """CMDB 比对结果。"""

    total_discovered: int = Field(default=0, description="发现设备总数")
    total_cmdb: int = Field(default=0, description="CMDB 设备总数")
    matched: int = Field(default=0, description="匹配数量")
    shadow_assets: int = Field(default=0, description="影子资产数量")
    offline_devices: int = Field(default=0, description="离线设备数量")
    compared_at: datetime = Field(default_factory=datetime.now, description="比对时间")


class OfflineDevice(BaseModel):
    """离线设备信息。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    ip_address: str = Field(..., description="IP 地址")
    offline_days: int = Field(default=0, description="离线天数")
    last_seen_at: datetime | None = Field(default=None, description="最后在线时间")
