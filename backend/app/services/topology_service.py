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
from app.core.enums import DeviceStatus
from app.core.logger import logger
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.crud.crud_topology import CRUDTopology
from app.models.device import Device
from app.models.topology import TopologyLink
from app.network.async_runner import run_async_tasks
from app.network.async_tasks import async_get_lldp_neighbors
from app.network.nornir_config import init_nornir_async
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
from app.services.base import DeviceCredentialMixin

# 拓扑缓存键
TOPOLOGY_CACHE_KEY = "ncm:topology:data"


class TopologyService(DeviceCredentialMixin):
    """网络拓扑服务类。"""

    def __init__(
        self,
        topology_crud: CRUDTopology,
        device_crud: CRUDDevice,
        credential_crud: CRUDCredential,
        redis_client: redis.Redis | None = None,
    ):
        self.topology_crud = topology_crud
        self.device_crud = device_crud
        self.credential_crud = credential_crud
        self._redis = redis_client
        # db 会在方法调用时临时设置，用于 DeviceCredentialMixin
        # 类型声明与 Mixin 保持一致，实际在 collect_lldp_all 中赋值
        self.db: AsyncSession = None  # type: ignore[assignment]

    async def collect_lldp_all(
        self,
        db: AsyncSession,
        device_ids: list[UUID] | None = None,
        skip_otp_manual: bool = False,
    ) -> TopologyCollectResult:
        """
        采集所有设备的 LLDP 邻居信息。

        Args:
            db: 数据库会话
            device_ids: 指定设备ID列表 (为空则采集所有活跃设备)
            skip_otp_manual: 是否跳过需要手动 OTP 的设备（用于定时任务）

        Returns:
            TopologyCollectResult: 采集结果
        """
        from app.core.enums import AuthType
        from app.core.exceptions import OTPRequiredException

        # 设置 db 以便 DeviceCredentialMixin 可以使用
        self.db = db

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

            # 构建 Nornir 主机数据，包含凭据获取
            hosts_data = []
            device_map: dict[str, Device] = {}
            failed_device_ids: list[str] = []

            # 收集所有需要 OTP 的设备组（避免多次触发 428）
            otp_required_groups: list[tuple[str, str]] = []  # [(dept_id, device_group), ...]

            for device in devices:
                if not device.ip_address:
                    continue

                # 跳过 OTP 手动认证的设备（用于定时任务）
                if skip_otp_manual and device.auth_type == AuthType.OTP_MANUAL.value:
                    logger.debug("跳过 OTP 手动认证设备", device=device.name)
                    result.failed_count += 1
                    result.results.append(
                        DeviceLLDPResult(
                            device_id=device.id,
                            device_name=device.name,
                            success=False,
                            error="跳过：需要手动 OTP 认证",
                        )
                    )
                    continue

                try:
                    # 通过 DeviceCredentialMixin 获取凭据
                    credential = await self._get_device_credential(device, failed_devices=failed_device_ids)

                    host_data = {
                        "name": device.name,
                        "hostname": device.ip_address,
                        "port": device.ssh_port or 22,
                        "username": credential.username,
                        "password": credential.password,
                        "platform": self._get_platform(device.vendor),
                    }
                    hosts_data.append(host_data)
                    # 使用 device.name 作为 key，与 Nornir host_name 保持一致
                    device_map[device.name] = device

                except OTPRequiredException as e:
                    # 收集所有需要 OTP 的设备组，最后统一抛出
                    group_key = (e.dept_id_str, e.device_group)
                    if group_key not in otp_required_groups:
                        otp_required_groups.append(group_key)
                    failed_device_ids.append(str(device.id))
                    result.failed_count += 1
                    result.results.append(
                        DeviceLLDPResult(
                            device_id=device.id,
                            device_name=device.name,
                            success=False,
                            error=f"需要 OTP: {e.device_group}",
                        )
                    )
                except Exception as e:
                    # 其他凭据错误，记录并跳过该设备
                    logger.warning("获取设备凭据失败", device=device.name, error=str(e))
                    failed_device_ids.append(str(device.id))
                    result.failed_count += 1
                    result.results.append(
                        DeviceLLDPResult(
                            device_id=device.id,
                            device_name=device.name,
                            success=False,
                            error=f"凭据获取失败: {e}",
                        )
                    )

            # 如果有需要 OTP 的设备组，抛出异常（只返回第一个）
            if otp_required_groups:
                first_group = otp_required_groups[0]
                raise OTPRequiredException(
                    dept_id=first_group[0],
                    device_group=first_group[1],
                    failed_devices=failed_device_ids,
                    message=f"需要输入 OTP 验证码（共 {len(otp_required_groups)} 个设备组需要验证）",
                )

            if not hosts_data:
                logger.warning("没有可采集的设备（所有设备凭据获取失败）")
                result.completed_at = datetime.now()
                return result

            # 创建异步 Inventory 并执行采集
            inventory = init_nornir_async(hosts_data)
            nornir_results = await run_async_tasks(
                inventory.hosts,
                async_get_lldp_neighbors,
                num_workers=min(50, len(hosts_data)),
            )

            # 转换异步结果为聚合格式
            aggregated = self._convert_lldp_results(nornir_results)

            if aggregated.get("otp_required"):
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
            for host_name, host_result in aggregated.get("results", {}).items():
                device = device_map.get(host_name)
                if not device:
                    logger.warning("设备映射未找到", host_name=host_name, device_map_keys=list(device_map.keys())[:5])
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

                    # 调试日志：查看 lldp_data 结构
                    if lldp_data:
                        raw_content = lldp_data.get("raw") or ""
                        raw_sample = raw_content[:500]
                        parsed_data = lldp_data.get("parsed")
                        logger.info(
                            "LLDP 数据调试",
                            device=device.name,
                            has_raw=bool(raw_content),
                            raw_length=len(raw_content),
                            raw_sample=raw_sample,
                            parsed_type=type(parsed_data).__name__ if parsed_data else None,
                            parsed_count=len(parsed_data) if isinstance(parsed_data, list) else 0,
                            parsed_sample=parsed_data[:2] if isinstance(parsed_data, list) and parsed_data else None,
                        )

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

            # 提交数据库更改
            await db.commit()

            # 清除拓扑缓存
            await self._invalidate_cache()

        except OTPRequiredException:
            # OTP 异常直接抛出，让任务失败并被 API 捕获
            raise
        except Exception as e:
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

    def _convert_lldp_results(self, results) -> dict[str, Any]:
        """
        将 AsyncRunner 结果转换为兼容格式。

        Args:
            results: AsyncRunner 返回的 AggregatedResult

        Returns:
            dict: 兼容原 aggregate_results 格式
        """
        from app.core.exceptions import OTPRequiredException

        aggregated: dict[str, Any] = {"results": {}, "success": 0, "failed": 0}
        otp_required_info: dict[str, Any] | None = None

        for host_name, multi_result in results.items():
            if multi_result.failed:
                exc = multi_result[0].exception if multi_result else None
                if isinstance(exc, OTPRequiredException):
                    otp_required_info = {
                        "otp_required": True,
                        "otp_dept_id": str(exc.dept_id) if exc.dept_id else None,
                        "otp_device_group": exc.device_group,
                        "otp_failed_device_ids": [str(d) for d in exc.failed_devices] if exc.failed_devices else [],
                    }
                aggregated["results"][host_name] = {
                    "status": "otp_required" if isinstance(exc, OTPRequiredException) else "failed",
                    "result": None,
                    "error": str(exc) if exc else "Unknown error",
                }
                aggregated["failed"] += 1
            else:
                result_data = multi_result[0].result if multi_result else None
                if result_data and result_data.get("success"):
                    aggregated["results"][host_name] = {
                        "status": "success",
                        "result": {"raw": result_data.get("raw"), "parsed": result_data.get("parsed")},
                        "error": None,
                    }
                    aggregated["success"] += 1
                else:
                    aggregated["results"][host_name] = {
                        "status": "failed",
                        "result": None,
                        "error": result_data.get("error") if result_data else "Unknown error",
                    }
                    aggregated["failed"] += 1

        if otp_required_info:
            aggregated.update(otp_required_info)

        return aggregated

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
                # TextFSM 解析后字段名为小写，优先使用小写
                neighbor = {
                    "local_interface": entry.get("local_interface") or entry.get("LOCAL_INTERFACE", ""),
                    "neighbor_interface": entry.get("neighbor_port_id")
                    or entry.get("neighbor_interface")
                    or entry.get("NEIGHBOR_PORT_ID", ""),
                    "neighbor_hostname": entry.get("neighbor_name")
                    or entry.get("neighbor")
                    or entry.get("NEIGHBOR_NAME", ""),
                    "neighbor_ip": entry.get("management_ip") or entry.get("MANAGEMENT_IP", ""),
                    "neighbor_description": entry.get("neighbor_description") or entry.get("SYSTEM_DESCRIPTION", ""),
                    "chassis_id": entry.get("chassis_id") or entry.get("CHASSIS_ID", ""),
                }
                neighbors.append(neighbor)

        return neighbors

    async def _match_target_device(
        self,
        db: AsyncSession,
        *,
        hostname: str | None = None,
        ip: str | None = None,
        mac: str | None = None,
    ) -> Device | None:
        """
        多维度匹配目标设备。

        匹配优先级：
        1. IP 精确匹配（最可靠）
        2. hostname 精确匹配
        3. hostname 模糊匹配（前缀/包含）

        Args:
            db: 数据库会话
            hostname: 邻居主机名（LLDP 上报）
            ip: 邻居管理 IP（LLDP 上报）
            mac: 邻居 MAC/Chassis ID（LLDP 上报，暂不用于匹配）

        Returns:
            Device | None: 匹配到的设备或 None
        """
        # 1. IP 精确匹配（最可靠）
        if ip:
            device = await self.device_crud.get_by_ip(db, ip_address=ip)
            if device:
                logger.debug("设备匹配成功（IP）", ip=ip, device_name=device.name)
                return device

        # 2. hostname 精确匹配
        if hostname:
            device = await self.device_crud.get_by_name(db, name=hostname)
            if device:
                logger.debug("设备匹配成功（hostname精确）", hostname=hostname, device_name=device.name)
                return device

            # 3. hostname 模糊匹配
            device = await self.device_crud.get_by_name_like(db, name=hostname)
            if device:
                logger.debug("设备匹配成功（hostname模糊）", hostname=hostname, device_name=device.name)
                return device

        # 未匹配到设备
        return None

    async def _save_device_topology(
        self,
        db: AsyncSession,
        device: Device,
        neighbors: list[dict],
    ) -> int:
        """
        保存设备拓扑链路。

        注意：不使用 @transactional() 装饰器，由调用方统一管理事务。

        Args:
            db: 数据库会话
            device: 源设备
            neighbors: 邻居列表

        Returns:
            保存的链路数量
        """
        # 使用字典去重，同一接口只保留第一个邻居（避免 UPSERT 冲突）
        links_by_interface: dict[str, TopologyLinkCreate] = {}
        now = datetime.now()

        for neighbor in neighbors:
            local_interface = neighbor.get("local_interface", "")
            if not local_interface:
                continue

            # 如果该接口已有邻居记录，跳过（保留第一个）
            if local_interface in links_by_interface:
                logger.debug(
                    "接口已有邻居记录，跳过重复",
                    device=device.name,
                    interface=local_interface,
                    existing_neighbor=links_by_interface[local_interface].target_hostname,
                    skipped_neighbor=neighbor.get("neighbor_hostname"),
                )
                continue

            # 尝试匹配目标设备（多维度匹配）
            target_ip = neighbor.get("neighbor_ip")
            target_hostname = neighbor.get("neighbor_hostname")
            target_mac = neighbor.get("chassis_id")

            target_device = await self._match_target_device(
                db,
                hostname=target_hostname,
                ip=target_ip,
                mac=target_mac,
            )
            target_device_id = target_device.id if target_device else None

            link_data = TopologyLinkCreate(
                source_device_id=device.id,
                source_interface=local_interface,
                target_device_id=target_device_id,
                target_interface=neighbor.get("neighbor_interface"),
                target_hostname=target_hostname,
                target_ip=target_ip,
                target_mac=target_mac,
                target_description=neighbor.get("neighbor_description"),
                link_type="lldp",
                collected_at=now,
            )
            links_by_interface[local_interface] = link_data

        links_data = list(links_by_interface.values())

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
            device_type=device.model,  # 设备型号
            device_group=group,
            status=device.status,  # 设备状态
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

        # 批量预加载目标设备信息，避免 N+1 查询
        target_ids = [link.target_device_id for link in links if link.target_device_id]
        target_devices = await self.device_crud.get_multi_by_ids(db, ids=target_ids) if target_ids else []
        target_map: dict[UUID, Device] = {d.id: d for d in target_devices}

        # 转换为响应格式
        neighbors: list[TopologyLinkResponse] = []
        for link in links:
            # 从预加载的映射中获取目标设备名称
            target_device_name = None
            if link.target_device_id and link.target_device_id in target_map:
                target_device_name = target_map[link.target_device_id].name

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
                target_device_name=target_device_name,
            )
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

    async def reset_topology(self, db: AsyncSession, *, hard_delete: bool = False) -> dict:
        """
        重置拓扑数据（清除所有链路）。

        Args:
            db: 数据库会话
            hard_delete: 是否硬删除

        Returns:
            删除统计信息
        """
        deleted_count = await self.topology_crud.clear_all_links(db, hard_delete=hard_delete)

        # 清除缓存
        await self._invalidate_cache()

        logger.info("拓扑数据已重置", deleted_links=deleted_count, hard_delete=hard_delete)

        return {
            "deleted_links": deleted_count,
            "hard_delete": hard_delete,
        }

    # ===== OTP 预检查 =====

    async def pre_check_otp_credentials(
        self,
        db: AsyncSession,
        device_ids: list[UUID] | None = None,
    ) -> None:
        """
        预检查设备凭据，确保 OTP 手动认证设备的凭据已就绪。

        此方法在提交 Celery 任务前调用，如果有 OTP 手动认证设备且
        缓存中没有有效的 OTP，会抛出 OTPRequiredException。

        Args:
            db: 数据库会话
            device_ids: 指定设备ID列表 (为空则检查所有活跃设备)

        Raises:
            OTPRequiredException: 需要用户输入 OTP 验证码
        """
        from app.core.enums import AuthType

        self.db = db

        # 获取待采集设备
        if device_ids:
            devices = await self.device_crud.get_multi_by_ids(db, ids=device_ids)
        else:
            devices, _ = await self.device_crud.get_multi_paginated(
                db, page=1, page_size=10000, status=DeviceStatus.ACTIVE
            )

        # 只检查 OTP 手动认证的设备
        otp_manual_devices = [d for d in devices if d.auth_type == AuthType.OTP_MANUAL.value]

        if not otp_manual_devices:
            # 没有 OTP 手动认证的设备，无需预检查
            return

        # 尝试获取第一个 OTP 手动设备的凭据
        # 如果缓存中没有有效的 OTP，会抛出 OTPRequiredException
        for device in otp_manual_devices:
            await self._get_device_credential(device)
            # 只需要检查一个设备即可，因为同部门同分组的设备共用 OTP
            break

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
