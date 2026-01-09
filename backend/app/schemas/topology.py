"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology.py
@DateTime: 2026-01-09 23:15:00
@Docs: 网络拓扑 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ===== 拓扑链路 CRUD =====


class TopologyLinkBase(BaseModel):
    """拓扑链路基础模型。"""

    source_interface: str = Field(..., description="源接口")
    target_interface: str | None = Field(default=None, description="目标接口")
    target_hostname: str | None = Field(default=None, description="目标主机名")
    target_ip: str | None = Field(default=None, description="目标管理IP")
    target_mac: str | None = Field(default=None, description="目标MAC地址")
    link_type: str = Field(default="lldp", description="链路类型")


class TopologyLinkCreate(TopologyLinkBase):
    """创建拓扑链路。"""

    source_device_id: UUID = Field(..., description="源设备ID")
    target_device_id: UUID | None = Field(default=None, description="目标设备ID")
    target_description: str | None = Field(default=None, description="目标描述")
    link_speed: str | None = Field(default=None, description="链路速率")
    link_status: str | None = Field(default=None, description="链路状态")
    collected_at: datetime = Field(default_factory=datetime.now, description="采集时间")


class TopologyLinkResponse(TopologyLinkBase):
    """拓扑链路响应。"""

    id: UUID
    source_device_id: UUID
    target_device_id: UUID | None = None
    target_description: str | None = None
    link_speed: str | None = None
    link_status: str | None = None
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

    # 关联的设备信息
    source_device_name: str | None = Field(default=None, description="源设备名称")
    source_device_ip: str | None = Field(default=None, description="源设备IP")
    target_device_name: str | None = Field(default=None, description="目标设备名称(CMDB)")

    class Config:
        from_attributes = True


# ===== vis.js 拓扑数据格式 =====


class TopologyNode(BaseModel):
    """拓扑节点 (vis.js 格式)。"""

    id: str = Field(..., description="节点ID (设备UUID或主机名)")
    label: str = Field(..., description="节点标签 (设备名称)")
    title: str | None = Field(default=None, description="鼠标悬停提示")
    group: str | None = Field(default=None, description="节点分组 (厂商/类型)")
    shape: str = Field(default="dot", description="节点形状")
    size: int = Field(default=25, description="节点大小")
    color: str | None = Field(default=None, description="节点颜色")

    # 附加信息
    ip: str | None = Field(default=None, description="管理IP")
    vendor: str | None = Field(default=None, description="厂商")
    device_type: str | None = Field(default=None, description="设备类型")
    device_group: str | None = Field(default=None, description="设备分组")
    in_cmdb: bool = Field(default=True, description="是否在CMDB中")


class TopologyEdge(BaseModel):
    """拓扑边 (vis.js 格式)。"""

    id: str | None = Field(default=None, description="边ID")
    from_: str = Field(..., alias="from", description="源节点ID")
    to: str = Field(..., description="目标节点ID")
    label: str | None = Field(default=None, description="边标签 (接口名)")
    title: str | None = Field(default=None, description="鼠标悬停提示")
    arrows: str = Field(default="to", description="箭头方向")
    color: str | None = Field(default=None, description="边颜色")
    dashes: bool = Field(default=False, description="是否虚线")
    width: int = Field(default=1, description="线宽")

    # 附加信息
    source_interface: str | None = Field(default=None, description="源接口")
    target_interface: str | None = Field(default=None, description="目标接口")
    link_type: str | None = Field(default=None, description="链路类型")

    model_config = {"populate_by_name": True}


class TopologyStats(BaseModel):
    """拓扑统计信息。"""

    total_nodes: int = Field(default=0, description="节点总数")
    total_edges: int = Field(default=0, description="边总数")
    cmdb_devices: int = Field(default=0, description="CMDB设备数")
    unknown_devices: int = Field(default=0, description="未知设备数")
    collected_at: datetime | None = Field(default=None, description="采集时间")
    cache_expires_at: datetime | None = Field(default=None, description="缓存过期时间")


class TopologyResponse(BaseModel):
    """拓扑数据响应 (vis.js 格式)。"""

    nodes: list[TopologyNode] = Field(default_factory=list, description="节点列表")
    edges: list[TopologyEdge] = Field(default_factory=list, description="边列表")
    stats: TopologyStats = Field(default_factory=TopologyStats, description="统计信息")


# ===== 采集请求和结果 =====


class TopologyCollectRequest(BaseModel):
    """拓扑采集请求。"""

    device_ids: list[UUID] | None = Field(default=None, description="指定设备ID列表 (为空则采集所有)")
    async_mode: bool = Field(default=True, description="是否异步执行")


class DeviceLLDPResult(BaseModel):
    """单设备 LLDP 采集结果。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    success: bool = Field(default=False, description="是否成功")
    neighbors_count: int = Field(default=0, description="邻居数量")
    neighbors: list[dict] = Field(default_factory=list, description="邻居列表")
    error: str | None = Field(default=None, description="错误信息")


class TopologyCollectResult(BaseModel):
    """拓扑采集任务结果。"""

    task_id: str | None = Field(default=None, description="Celery 任务ID")
    total_devices: int = Field(default=0, description="采集设备数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
    total_links: int = Field(default=0, description="发现链路数")
    results: list[DeviceLLDPResult] = Field(default_factory=list, description="各设备结果")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")


class TopologyTaskStatus(BaseModel):
    """拓扑采集任务状态。"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(default=0, description="进度百分比")
    result: TopologyCollectResult | None = Field(default=None, description="采集结果")
    error: str | None = Field(default=None, description="错误信息")


# ===== 邻居查询 =====


class DeviceNeighborsResponse(BaseModel):
    """设备邻居响应。"""

    device_id: UUID = Field(..., description="设备ID")
    device_name: str | None = Field(default=None, description="设备名称")
    neighbors: list[TopologyLinkResponse] = Field(default_factory=list, description="邻居链路列表")
    total: int = Field(default=0, description="邻居总数")
