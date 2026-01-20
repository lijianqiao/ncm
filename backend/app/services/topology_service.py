"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: topology_service.py
@DateTime: 2026-01-09 23:40:00
@Docs: 网络拓扑服务 (Topology Service).

提供 LLDP 拓扑采集、拓扑构建和 vis.js 格式数据输出。
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decorator import transactional
from app.core.enums import DeviceStatus
from app.core.logger import logger
from app.crud.crud_device import CRUDDevice
from app.crud.crud_topology import CRUDTopology
from app.models.device import Device
from app.models.topology import TopologyLink
from app.network.nornir_config import init_nornir
from app.network.nornir_tasks import aggregate_results, get_lldp_neighbors
from app.schemas.topology import (
    DeviceLLDPResult,
    DeviceNeighborsResponse,
    TopologyCollectResult,
    TopologyEdge,
    TopologyLinkCreate,
    TopologyLinkResponse,
    TopologyNode,
    TopologyResponse,
    TopologyStats,
)

# 拓扑缓存键
TOPOLOGY_CACHE_KEY = "ncm:topology:data"


class TopologyService:
    """网络拓扑服务类。"""

    def __init__(
        self,
        topology_crud: CRUDTopology,
        device_crud: CRUDDevice,
        redis_client: redis.Redis | None = None,
    ):
        self.topology_crud = topology_crud
        self.device_crud = device_crud
        self._redis = redis_client

    async def collect_lldp_all(
        self,
        db: AsyncSession,
        device_ids: list[UUID] | None = None,
    ) -> TopologyCollectResult:
        """
        采集所有设备的 LLDP 邻居信息。

        Args:
            db: 数据库会话
            device_ids: 指定设备ID列表 (为空则采集所有活跃设备)

        Returns:
            TopologyCollectResult: 采集结果
        """
        started_at = datetime.now()
        result = TopologyCollectResult(
            started_at=started_at,
            results=[],
        )

        try:
            # 获取待采集设备
            if device_ids:
                devices = await self.device_crud.get_multi_by_ids(db, ids=device_ids)
            else:
                devices, _ = await self.device_crud.get_multi_paginated(
                    db, page=1, page_size=10000, status=DeviceStatus.ACTIVE
                )

            result.total_devices = len(devices)

            if not devices:
                logger.warning("没有找到需要采集 LLDP 的设备")
                result.completed_at = datetime.now()
                return result

            # 构建 Nornir 主机数据
            hosts_data = []
            device_map: dict[str, Device] = {}

            for device in devices:
                if not device.ip_address:
                    continue

                host_data = {
                    "name": device.name,
                    "hostname": device.ip_address,
                    "port": device.ssh_port or 22,
                    "username": device.username or "",
                    "password": "",  # 密码需要通过凭据服务获取
                    "platform": self._get_platform(device.vendor),
                }
                hosts_data.append(host_data)
                device_map[device.ip_address] = device

            # 创建 Nornir 实例并执行采集
            nr = init_nornir(hosts_data)
            nornir_results = nr.run(task=get_lldp_neighbors)
            aggregated = aggregate_results(nornir_results)

            if aggregated.get("otp_required"):
                from app.core.exceptions import OTPRequiredException

                dept_id_str = aggregated.get("otp_dept_id")
                device_group = aggregated.get("otp_device_group")

                if dept_id_str and device_group:
                    raise OTPRequiredException(
                        dept_id=UUID(str(dept_id_str)),
                        device_group=str(device_group),
                        failed_devices=aggregated.get("otp_failed_device_ids"),
                        message="OTP 认证失败",
                    )
                else:
                    logger.warning("Nornir 结果显示 OTP 失败但缺少部门信息", aggregated=aggregated)

            # 处理采集结果
            total_links = 0
            for host_ip, host_result in aggregated.get("results", {}).items():
                device = device_map.get(host_ip)
                if not device:
                    continue

                device_result = DeviceLLDPResult(
                    device_id=device.id,
                    device_name=device.name,
                    success=host_result.get("status") == "success",
                )

                if device_result.success:
                    result.success_count += 1
                    # 解析 LLDP 邻居
                    lldp_data = host_result.get("result", {})
                    neighbors = self._parse_lldp_result(lldp_data)
                    device_result.neighbors = neighbors
                    device_result.neighbors_count = len(neighbors)

                    # 保存拓扑链路
                    saved_count = await self._save_device_topology(db, device=device, neighbors=neighbors)
                    total_links += saved_count
                else:
                    result.failed_count += 1
                    device_result.error = host_result.get("error", "Unknown error")

                result.results.append(device_result)

            result.total_links = total_links
            result.completed_at = datetime.now()

            # 清除拓扑缓存
            await self._invalidate_cache()

        except Exception as e:
            # 如果是 OTP 异常，直接抛出，让任务失败并被 API 捕获
            from app.core.exceptions import OTPRequiredException

            if isinstance(e, OTPRequiredException):
                raise

            logger.error("LLDP 采集失败", error=str(e))
            result.completed_at = datetime.now()

        return result

    def _get_platform(self, vendor: str | None) -> str:
        """
        根据厂商获取 Nornir 平台标识。

        Args:
            vendor: 厂商名称

        Returns:
            平台标识
        """
        platform_map = {
            "h3c": "hp_comware",
            "huawei": "huawei_vrp",
            "cisco": "cisco_ios",
        }
        return platform_map.get(vendor or "", "cisco_ios")

    def _parse_lldp_result(self, lldp_data: dict[str, Any]) -> list[dict]:
        """
        解析 LLDP 采集结果。

        Args:
            lldp_data: LLDP 原始数据 (TextFSM 解析后)

        Returns:
            邻居列表
        """
        neighbors: list[dict] = []

        # 处理解析后的数据
        parsed = lldp_data.get("parsed")
        if not parsed:
            return neighbors

        if isinstance(parsed, list):
            for entry in parsed:
                neighbor = {
                    "local_interface": entry.get("local_interface", entry.get("LOCAL_INTERFACE", "")),
                    "neighbor_interface": entry.get("neighbor_interface", entry.get("NEIGHBOR_PORT_ID", "")),
                    "neighbor_hostname": entry.get("neighbor", entry.get("NEIGHBOR_NAME", "")),
                    "neighbor_ip": entry.get("management_ip", entry.get("MANAGEMENT_IP", "")),
                    "neighbor_description": entry.get("neighbor_description", entry.get("SYSTEM_DESCRIPTION", "")),
                    "chassis_id": entry.get("chassis_id", entry.get("CHASSIS_ID", "")),
                }
                neighbors.append(neighbor)

        return neighbors

    @transactional()
    async def _save_device_topology(
        self,
        db: AsyncSession,
        device: Device,
        neighbors: list[dict],
    ) -> int:
        """
        保存设备拓扑链路。

        Args:
            db: 数据库会话
            device: 源设备
            neighbors: 邻居列表

        Returns:
            保存的链路数量
        """
        links_data: list[TopologyLinkCreate] = []
        now = datetime.now()

        for neighbor in neighbors:
            local_interface = neighbor.get("local_interface", "")
            if not local_interface:
                continue

            # 尝试匹配目标设备
            target_device_id = None
            target_ip = neighbor.get("neighbor_ip")
            if target_ip:
                target_device = await self.device_crud.get_by_ip(db, ip_address=target_ip)
                if target_device:
                    target_device_id = target_device.id

            link_data = TopologyLinkCreate(
                source_device_id=device.id,
                source_interface=local_interface,
                target_device_id=target_device_id,
                target_interface=neighbor.get("neighbor_interface"),
                target_hostname=neighbor.get("neighbor_hostname"),
                target_ip=target_ip,
                target_mac=neighbor.get("chassis_id"),
                target_description=neighbor.get("neighbor_description"),
                link_type="lldp",
                collected_at=now,
            )
            links_data.append(link_data)

        # 刷新设备拓扑
        _, created_count = await self.topology_crud.refresh_device_topology(
            db, device_id=device.id, links_data=links_data
        )

        return created_count

    async def build_topology(self, db: AsyncSession) -> TopologyResponse:
        """
        构建拓扑数据 (vis.js 格式)。

        Args:
            db: 数据库会话

        Returns:
            TopologyResponse: vis.js 格式的拓扑数据
        """
        # 尝试从缓存获取
        cached = await self._get_cached_topology()
        if cached:
            return cached

        # 从数据库构建
        nodes: list[TopologyNode] = []
        edges: list[TopologyEdge] = []
        node_ids: set[str] = set()

        # 获取所有链路
        links = await self.topology_crud.get_all_links(db, limit=5000)

        # 获取所有相关设备
        device_ids = await self.topology_crud.get_unique_devices_in_topology(db)
        devices_list = await self.device_crud.get_multi_by_ids(db, ids=list(device_ids))
        device_map: dict[UUID, Device] = {d.id: d for d in devices_list}

        # 构建节点和边
        for link in links:
            # 源节点
            source_id = str(link.source_device_id)
            if source_id not in node_ids:
                source_device = device_map.get(link.source_device_id)
                if source_device:
                    nodes.append(self._create_node_from_device(source_device))
                    node_ids.add(source_id)

            # 目标节点
            if link.target_device_id:
                target_id = str(link.target_device_id)
                if target_id not in node_ids:
                    target_device = device_map.get(link.target_device_id)
                    if target_device:
                        nodes.append(self._create_node_from_device(target_device))
                        node_ids.add(target_id)
            else:
                # 未知设备节点
                target_id = link.target_hostname or link.target_ip or f"unknown_{link.id}"
                if target_id not in node_ids:
                    nodes.append(
                        TopologyNode(
                            id=target_id,
                            label=link.target_hostname or link.target_ip or "Unknown",
                            title=f"IP: {link.target_ip or 'N/A'}",
                            group="unknown",
                            shape="triangle",
                            size=20,
                            ip=link.target_ip,
                            in_cmdb=False,
                        )
                    )
                    node_ids.add(target_id)

            # 边
            edge_label = f"{link.source_interface}"
            if link.target_interface:
                edge_label += f" → {link.target_interface}"

            edge_data = {
                "id": str(link.id),
                "from": str(link.source_device_id),
                "to": target_id,
                "label": edge_label,
                "title": f"Type: {link.link_type}",
                "source_interface": link.source_interface,
                "target_interface": link.target_interface,
                "link_type": link.link_type,
            }
            edges.append(TopologyEdge.model_validate(edge_data))

        # 统计信息
        cmdb_count = sum(1 for n in nodes if n.in_cmdb)
        stats = TopologyStats(
            total_nodes=len(nodes),
            total_edges=len(edges),
            cmdb_devices=cmdb_count,
            unknown_devices=len(nodes) - cmdb_count,
            collected_at=datetime.now(),
            cache_expires_at=datetime.now() + timedelta(seconds=settings.TOPOLOGY_CACHE_TTL),
        )

        response = TopologyResponse(nodes=nodes, edges=edges, stats=stats)

        # 缓存结果
        await self._cache_topology(response)

        return response

    def _create_node_from_device(self, device: Device) -> TopologyNode:
        """
        从设备创建拓扑节点。

        Args:
            device: 设备对象

        Returns:
            TopologyNode
        """
        # 根据设备分组设置形状和颜色
        shape_map = {
            "core": "diamond",
            "distribution": "square",
            "access": "dot",
        }
        color_map = {
            "core": "#e74c3c",
            "distribution": "#f39c12",
            "access": "#3498db",
        }

        group = device.device_group or "access"

        return TopologyNode(
            id=str(device.id),
            label=device.name,
            title=f"IP: {device.ip_address}\nVendor: {device.vendor or 'N/A'}",
            group=group,
            shape=shape_map.get(group, "dot"),
            size=30 if group == "core" else 25,
            color=color_map.get(group),
            ip=device.ip_address,
            vendor=device.vendor,
            device_type=None,  # Device 模型无 device_type 字段
            device_group=group,
            in_cmdb=True,
        )

    async def get_device_neighbors(self, db: AsyncSession, device_id: UUID) -> DeviceNeighborsResponse:
        """
        获取设备邻居列表。

        Args:
            db: 数据库会话
            device_id: 设备ID

        Returns:
            DeviceNeighborsResponse
        """
        device = await self.device_crud.get(db, id=device_id)
        if not device:
            return DeviceNeighborsResponse(
                device_id=device_id,
                neighbors=[],
                total=0,
            )

        links = await self.topology_crud.get_device_neighbors(db, device_id=device_id)

        # 转换为响应格式
        neighbors: list[TopologyLinkResponse] = []
        for link in links:
            response = TopologyLinkResponse(
                id=link.id,
                source_device_id=link.source_device_id,
                source_interface=link.source_interface,
                target_device_id=link.target_device_id,
                target_interface=link.target_interface,
                target_hostname=link.target_hostname,
                target_ip=link.target_ip,
                target_mac=link.target_mac,
                target_description=link.target_description,
                link_type=link.link_type,
                link_speed=link.link_speed,
                link_status=link.link_status,
                collected_at=link.collected_at,
                created_at=link.created_at,
                updated_at=link.updated_at,
                source_device_name=device.name,
                source_device_ip=device.ip_address,
            )

            # 获取目标设备名称
            if link.target_device_id:
                target_device = await self.device_crud.get(db, id=link.target_device_id)
                if target_device:
                    response.target_device_name = target_device.name

            neighbors.append(response)

        return DeviceNeighborsResponse(
            device_id=device_id,
            device_name=device.name,
            neighbors=neighbors,
            total=len(neighbors),
        )

    async def get_all_links(
        self, db: AsyncSession, page: int = 1, page_size: int = 50
    ) -> tuple[list[TopologyLink], int]:
        """
        获取所有拓扑链路 (分页)。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量

        Returns:
            (links, total): 链路列表和总数
        """
        skip = (page - 1) * page_size
        links = await self.topology_crud.get_all_links(db, skip=skip, limit=page_size)
        total = await self.topology_crud.count_links(db)
        return links, total

    async def export_topology(self, db: AsyncSession) -> dict[str, Any]:
        """
        导出拓扑数据 (JSON 格式)。

        Args:
            db: 数据库会话

        Returns:
            导出的拓扑数据
        """
        topology = await self.build_topology(db)

        return {
            "exported_at": datetime.now().isoformat(),
            "nodes": [n.model_dump() for n in topology.nodes],
            "edges": [e.model_dump(by_alias=True) for e in topology.edges],
            "stats": topology.stats.model_dump(),
        }

    # ===== 缓存方法 =====

    async def _get_cached_topology(self) -> TopologyResponse | None:
        """从 Redis 获取缓存的拓扑数据。"""
        if not self._redis:
            return None

        try:
            data = await self._redis.get(TOPOLOGY_CACHE_KEY)
            if data:
                return TopologyResponse.model_validate_json(data)
        except Exception as e:
            logger.warning("获取拓扑缓存失败", error=str(e))

        return None

    async def _cache_topology(self, topology: TopologyResponse) -> None:
        """缓存拓扑数据到 Redis。"""
        if not self._redis:
            return

        try:
            await self._redis.setex(
                TOPOLOGY_CACHE_KEY,
                settings.TOPOLOGY_CACHE_TTL,
                topology.model_dump_json(),
            )
        except Exception as e:
            logger.warning("缓存拓扑数据失败", error=str(e))

    async def _invalidate_cache(self) -> None:
        """清除拓扑缓存。"""
        if not self._redis:
            return

        try:
            await self._redis.delete(TOPOLOGY_CACHE_KEY)
        except Exception as e:
            logger.warning("清除拓扑缓存失败", error=str(e))
