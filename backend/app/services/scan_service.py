"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: scan_service.py
@DateTime: 2026-01-09 23:30:00
@Docs: 网络扫描服务 (Scan Service).

提供 Nmap/Masscan 扫描功能，以及扫描结果与 CMDB 比对。
"""

import asyncio
import shutil
import subprocess
from datetime import datetime
from typing import Any
from uuid import UUID

import nmap
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decorator import transactional
from app.core.encryption import decrypt_snmp_secret
from app.core.enums import DeviceGroup, DeviceStatus, DeviceVendor, DiscoveryStatus
from app.core.logger import logger
from app.crud.crud_device import CRUDDevice
from app.crud.crud_discovery import CRUDDiscovery
from app.crud.crud_snmp_credential import dept_snmp_credential as dept_snmp_credential_crud
from app.models.device import Device
from app.models.discovery import Discovery
from app.schemas.discovery import (
    CMDBCompareResult,
    DiscoveryCreate,
    OfflineDevice,
    ScanHost,
    ScanResult,
)
from app.services.snmp_service import SnmpService, SnmpV2cCredential


class ScanService:
    """网络扫描服务类。"""

    def __init__(
        self,
        discovery_crud: CRUDDiscovery,
        device_crud: CRUDDevice,
    ):
        self.discovery_crud = discovery_crud
        self.device_crud = device_crud

    async def nmap_scan(
        self,
        subnet: str,
        ports: str | None = None,
        arguments: str = "-sS -sV -O --host-timeout 30s",
    ) -> ScanResult:
        """
        使用 Nmap 扫描网段。

        Args:
            subnet: 网段 (CIDR 格式)
            ports: 扫描端口 (如 "22,23,80,443")
            arguments: Nmap 参数

        Returns:
            ScanResult: 扫描结果
        """
        started_at = datetime.now()
        result = ScanResult(
            subnet=subnet,
            scan_type="nmap",
            started_at=started_at,
        )

        if not self.is_nmap_available():
            result.error = "Nmap 未安装或不在 PATH 中，请安装 Nmap 并将 nmap 加入 PATH，或选择 masscan"
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())
            return result

        try:
            # 在线程池中运行 nmap 扫描 (避免阻塞事件循环)
            scan_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_nmap_scan,
                subnet,
                ports or settings.SCAN_DEFAULT_PORTS,
                arguments,
            )

            # 解析扫描结果
            hosts = self._parse_nmap_result(scan_result)
            result.hosts = hosts
            result.hosts_found = len(hosts)
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())

        except Exception as e:
            logger.error(f"Nmap 扫描失败: {subnet}", error=str(e))
            result.error = f"Nmap 扫描失败: {e}"
            result.completed_at = datetime.now()

        return result

    async def nmap_ping_scan(self, subnet: str) -> ScanResult:
        started_at = datetime.now()
        result = ScanResult(
            subnet=subnet,
            scan_type="nmap",
            started_at=started_at,
        )

        if not self.is_nmap_available():
            result.error = "Nmap 未安装或不在 PATH 中，请安装 Nmap 并将 nmap 加入 PATH，或选择 masscan"
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())
            return result

        try:
            hosts = await asyncio.get_event_loop().run_in_executor(None, self._run_nmap_ping_scan, subnet)
            result.hosts = hosts
            result.hosts_found = len(hosts)
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())
        except Exception as e:
            logger.error(f"Nmap 存活探测失败: {subnet}", error=str(e))
            result.error = f"Nmap 存活探测失败: {e}"
            result.completed_at = datetime.now()

        return result

    def is_nmap_available(self) -> bool:
        return shutil.which("nmap") is not None

    def _run_nmap_ping_scan(self, subnet: str) -> list[ScanHost]:
        cmd = [
            "nmap",
            "-sn",
            "-n",
            "--max-retries",
            "1",
            "--host-timeout",
            "5s",
            subnet,
            "-oG",
            "-",
        ]

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=min(int(settings.SCAN_TIMEOUT), 90),
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Timeout from nmap process") from e
        except FileNotFoundError as e:
            raise RuntimeError("Nmap 未安装，请先安装 nmap") from e

        hosts: list[ScanHost] = []
        for line in (process.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("Host:"):
                continue
            if "Status: Up" not in line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue
            ip = parts[1]
            hosts.append(ScanHost(ip_address=ip, status="up"))

        return hosts

    def _run_nmap_scan(self, subnet: str, ports: str, arguments: str) -> dict[str, Any]:
        """
        运行 Nmap 扫描 (同步方法，在线程池中执行)。

        Args:
            subnet: 网段
            ports: 端口
            arguments: Nmap 参数

        Returns:
            扫描结果字典
        """
        nm = nmap.PortScanner()
        nm.scan(hosts=subnet, ports=ports, arguments=arguments, timeout=settings.SCAN_TIMEOUT)
        return {
            "hosts": nm.all_hosts(),
            "scan_info": nm.scaninfo(),
            "scan_stats": nm.scanstats(),
            "csv": nm.csv(),
            "raw": {host: nm[host] for host in nm.all_hosts()},
        }

    def _parse_nmap_result(self, scan_result: dict[str, Any]) -> list[ScanHost]:
        """
        解析 Nmap 扫描结果。

        Args:
            scan_result: Nmap 原始结果

        Returns:
            ScanHost 列表
        """
        hosts: list[ScanHost] = []
        raw_data = scan_result.get("raw", {})

        for ip, host_data in raw_data.items():
            # 获取 MAC 地址和厂商
            mac_address = None
            vendor = None
            addresses = host_data.get("addresses", {})
            if "mac" in addresses:
                mac_address = addresses["mac"]
            vendor_info = host_data.get("vendor", {})
            if mac_address and mac_address in vendor_info:
                vendor = vendor_info[mac_address]

            # 获取主机名
            hostname = None
            hostnames = host_data.get("hostnames", [])
            if hostnames and hostnames[0].get("name"):
                hostname = hostnames[0]["name"]

            # 获取操作系统信息
            os_info = None
            osmatch = host_data.get("osmatch", [])
            if osmatch:
                os_info = osmatch[0].get("name", "")

            # 获取开放端口
            open_ports: dict[int, str] = {}
            for proto in ["tcp", "udp"]:
                if proto in host_data:
                    for port, port_data in host_data[proto].items():
                        if port_data.get("state") == "open":
                            service = port_data.get("name", "unknown")
                            open_ports[int(port)] = service

            # 尝试提取 SSH banner（基于 nmap service 指纹信息）
            ssh_banner = None
            tcp_data = host_data.get("tcp", {})
            if isinstance(tcp_data, dict) and 22 in tcp_data:
                p22 = tcp_data.get(22) or {}
                if isinstance(p22, dict) and p22.get("state") == "open":
                    parts = [
                        p22.get("product"),
                        p22.get("version"),
                        p22.get("extrainfo"),
                    ]
                    parts = [p for p in parts if isinstance(p, str) and p.strip()]
                    if parts:
                        ssh_banner = " ".join(parts)

            # vendor 兜底：没有 MAC/OUI 时，根据 os_info/ssh_banner 推断
            if not vendor:
                try:
                    from app.network.platform_config import (
                        detect_vendor_from_banner,
                        detect_vendor_from_version,
                    )

                    if ssh_banner:
                        vendor = detect_vendor_from_banner(ssh_banner)
                    if not vendor and os_info:
                        vendor = detect_vendor_from_version(os_info)
                except Exception:
                    vendor = vendor

            # 获取状态
            status = host_data.get("status", {}).get("state", "unknown")

            hosts.append(
                ScanHost(
                    ip_address=ip,
                    mac_address=mac_address,
                    hostname=hostname,
                    vendor=vendor,
                    os_info=os_info,
                    open_ports=open_ports if open_ports else None,
                    ssh_banner=ssh_banner,
                    status=status,
                )
            )

        return hosts

    async def masscan_scan(
        self,
        subnet: str,
        ports: str | None = None,
        rate: int | None = None,
    ) -> ScanResult:
        """
        使用 Masscan 快速扫描网段 (仅存活探测)。

        Args:
            subnet: 网段 (CIDR 格式)
            ports: 扫描端口
            rate: 扫描速率 (packets/sec)

        Returns:
            ScanResult: 扫描结果
        """
        started_at = datetime.now()
        result = ScanResult(
            subnet=subnet,
            scan_type="masscan",
            started_at=started_at,
        )

        if not self.is_masscan_available():
            result.error = "Masscan 未安装或不在 PATH 中，请先安装 masscan 或选择 nmap"
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())
            return result

        try:
            ports = ports or settings.SCAN_DEFAULT_PORTS
            rate = rate or settings.SCAN_RATE

            # 在线程池中运行 masscan
            hosts = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_masscan,
                subnet,
                ports,
                rate,
            )

            result.hosts = hosts
            result.hosts_found = len(hosts)
            result.completed_at = datetime.now()
            result.duration_seconds = int((result.completed_at - started_at).total_seconds())

        except Exception as e:
            logger.error(f"Masscan 扫描失败: {subnet}", error=str(e))
            result.error = str(e)
            result.completed_at = datetime.now()

        return result

    def is_masscan_available(self) -> bool:
        return shutil.which("masscan") is not None

    def resolve_scan_type(self, scan_type: str) -> str:
        scan_type = (scan_type or "").strip().lower()

        if scan_type in {"nmap", "masscan"}:
            return scan_type

        if scan_type in {"auto", ""}:
            if self.is_masscan_available():
                return "masscan"
            if self.is_nmap_available():
                return "nmap"
            return "none"

        raise ValueError("scan_type 仅支持 auto/nmap/masscan")

    def _run_masscan(self, subnet: str, ports: str, rate: int) -> list[ScanHost]:
        """
        运行 Masscan 扫描 (同步方法)。

        Args:
            subnet: 网段
            ports: 端口
            rate: 速率

        Returns:
            ScanHost 列表
        """
        hosts: list[ScanHost] = []

        try:
            # 构建 masscan 命令
            cmd = [
                "masscan",
                subnet,
                "-p",
                ports,
                "--rate",
                str(rate),
                "-oG",
                "-",  # Grepable 输出到 stdout
            ]

            # 执行命令
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.SCAN_TIMEOUT,
            )

            # 解析输出
            for line in process.stdout.splitlines():
                if line.startswith("Host:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1]
                        # 解析端口
                        open_ports: dict[int, str] = {}
                        if "Ports:" in line:
                            port_section = line.split("Ports:")[1].strip()
                            for port_info in port_section.split(","):
                                port_parts = port_info.strip().split("/")
                                if len(port_parts) >= 1:
                                    try:
                                        port = int(port_parts[0])
                                        open_ports[port] = "unknown"
                                    except ValueError:
                                        pass

                        hosts.append(
                            ScanHost(
                                ip_address=ip,
                                open_ports=open_ports if open_ports else None,
                                status="up",
                            )
                        )

        except subprocess.TimeoutExpired:
            logger.warning(f"Masscan 超时: {subnet}")
        except FileNotFoundError as e:
            logger.error("Masscan 未安装或不在 PATH 中")
            raise RuntimeError("Masscan 未安装，请先安装 masscan") from e

        return hosts

    @transactional()
    async def process_scan_result(
        self,
        db: AsyncSession,
        scan_result: ScanResult,
        scan_task_id: str | None = None,
        snmp_cred_id: UUID | None = None,
    ) -> int:
        """
        处理扫描结果，更新 Discovery 表。

        Args:
            db: 数据库会话
            scan_result: 扫描结果
            scan_task_id: 扫描任务ID

        Returns:
            处理的主机数量
        """
        snmp_results: dict[str, dict[str, Any]] = {}
        try:
            snmp_cred = None
            if snmp_cred_id:
                snmp_cred = await dept_snmp_credential_crud.get(db, id=snmp_cred_id)
                if snmp_cred and snmp_cred.is_deleted:
                    snmp_cred = None

            if snmp_cred and snmp_cred.snmp_version == "v2c" and snmp_cred.community_encrypted:
                community = decrypt_snmp_secret(snmp_cred.community_encrypted)
                snmp_service = SnmpService()
                cred = SnmpV2cCredential(community=community, port=snmp_cred.port)
                sem = asyncio.Semaphore(settings.SNMP_MAX_CONCURRENCY)

                async def _enrich(ip: str, open_ports: dict[int, str] | None):
                    async with sem:
                        r = await snmp_service.enrich_basic(ip, cred)
                        return ip, r

                tasks = [_enrich(h.ip_address, h.open_ports) for h in scan_result.hosts]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for item in results:
                    try:
                        ip, r = item  # type: ignore[misc]
                    except Exception:
                        continue
                    if r is None:
                        continue
                    snmp_results[ip] = {
                        "snmp_sysname": r.sys_name,
                        "snmp_sysdescr": r.sys_descr,
                        "serial_number": r.serial_number,
                        "bridge_mac": r.bridge_mac,
                        "interface_mac": r.interface_mac,
                        "interface_name": r.interface_name,
                        "snmp_ok": r.ok,
                        "snmp_error": r.error,
                    }
            elif snmp_cred_id:
                logger.warning("SNMP 凭据不可用或不支持 v2c", snmp_cred_id=str(snmp_cred_id))
        except Exception as e:
            logger.warning("SNMP 补全失败（已忽略，不影响扫描入库）", error=str(e))

        data_list: list[DiscoveryCreate] = []

        for host in scan_result.hosts:
            try:
                sys_descr = snmp_results.get(host.ip_address, {}).get("snmp_sysdescr") if snmp_results else None
                sys_name = snmp_results.get(host.ip_address, {}).get("snmp_sysname") if snmp_results else None
                inferred_vendor = None
                if isinstance(sys_descr, str) and sys_descr:
                    s = sys_descr.lower()
                    if "cisco" in s:
                        inferred_vendor = "cisco"
                    elif "huawei" in s:
                        inferred_vendor = "huawei"
                    elif "h3c" in s:
                        inferred_vendor = "h3c"
                    elif "juniper" in s:
                        inferred_vendor = "juniper"
                    elif "arista" in s:
                        inferred_vendor = "arista"
                    elif "nokia" in s or "alcatel" in s:
                        inferred_vendor = "nokia"
                    elif "ruijie" in s:
                        inferred_vendor = "ruijie"
                    elif "mikrotik" in s:
                        inferred_vendor = "mikrotik"
                    elif "dell" in s:
                        inferred_vendor = "dell"
                    elif "hewlett-packard" in s or "hp " in s:
                        inferred_vendor = "hp"
                    elif "aruba" in s:
                        inferred_vendor = "aruba"

                data_list.append(
                    DiscoveryCreate(
                        ip_address=host.ip_address,
                        mac_address=host.mac_address
                        or (
                            snmp_results.get(host.ip_address, {}).get("interface_mac")
                            or snmp_results.get(host.ip_address, {}).get("bridge_mac")
                            if snmp_results
                            else None
                        ),
                        vendor=host.vendor or inferred_vendor,
                        hostname=(sys_name if isinstance(sys_name, str) and sys_name else None) or host.hostname,
                        os_info=host.os_info,
                        serial_number=snmp_results.get(host.ip_address, {}).get("serial_number")
                        if snmp_results
                        else None,
                        open_ports=host.open_ports,
                        ssh_banner=getattr(host, "ssh_banner", None),
                        scan_source=scan_result.scan_type,
                        scan_task_id=scan_task_id,
                        snmp_sysname=snmp_results.get(host.ip_address, {}).get("snmp_sysname")
                        if snmp_results
                        else None,
                        snmp_sysdescr=snmp_results.get(host.ip_address, {}).get("snmp_sysdescr")
                        if snmp_results
                        else None,
                        snmp_ok=snmp_results.get(host.ip_address, {}).get("snmp_ok") if snmp_results else None,
                        snmp_error=snmp_results.get(host.ip_address, {}).get("snmp_error") if snmp_results else None,
                    )
                )
            except Exception as e:
                logger.error(f"构造发现数据失败: {host.ip_address}", error=str(e))

        if not data_list:
            return 0

        try:
            return await self.discovery_crud.upsert_many(
                db,
                data_list=data_list,
                scan_source=scan_result.scan_type,
                scan_task_id=scan_task_id,
            )
        except Exception as e:
            logger.error("批量处理扫描结果失败", error=str(e))
            raise

    @transactional()
    async def compare_with_cmdb(self, db: AsyncSession) -> CMDBCompareResult:
        """
        将发现记录与 CMDB (Device 表) 比对。

        Args:
            db: 数据库会话

        Returns:
            CMDBCompareResult: 比对结果
        """
        result = CMDBCompareResult(compared_at=datetime.now())

        # 获取所有发现记录
        discoveries, total_discovered = await self.discovery_crud.get_multi_paginated(db, page=1, page_size=10000)
        result.total_discovered = total_discovered

        # 获取所有设备
        devices, total_cmdb = await self.device_crud.get_multi_paginated(db, page=1, page_size=10000)
        result.total_cmdb = total_cmdb

        # 构建设备 IP 索引
        device_ip_map: dict[str, Device] = {d.ip_address: d for d in devices}

        # 比对发现记录
        matched_count = 0
        shadow_count = 0

        for discovery in discoveries:
            if discovery.ip_address in device_ip_map:
                # 匹配成功
                device = device_ip_map[discovery.ip_address]
                if discovery.status != DiscoveryStatus.MATCHED.value:
                    await self.discovery_crud.set_matched_device(db, id=discovery.id, device_id=device.id)
                matched_count += 1
            else:
                # 影子资产
                if discovery.status != DiscoveryStatus.SHADOW.value:
                    await self.discovery_crud.update_status(db, id=discovery.id, status=DiscoveryStatus.SHADOW)
                shadow_count += 1

        result.matched = matched_count
        result.shadow_assets = shadow_count

        # 检测离线设备 (CMDB 中有但扫描未发现)
        discovered_ips = {d.ip_address for d in discoveries}
        offline_count = 0
        for device in devices:
            if device.ip_address not in discovered_ips:
                offline_count += 1

        result.offline_devices = offline_count

        return result

    async def detect_offline_devices(self, db: AsyncSession, days_threshold: int = 7) -> list[OfflineDevice]:
        """
        检测离线设备 (CMDB 中存在但长时间未扫描到)。

        Args:
            db: 数据库会话
            days_threshold: 离线天数阈值

        Returns:
            OfflineDevice 列表
        """
        offline_devices: list[OfflineDevice] = []

        # 获取所有活跃设备
        devices, _ = await self.device_crud.get_multi_paginated(db, page=1, page_size=10000, status=DeviceStatus.ACTIVE)

        for device in devices:
            # 查找对应的发现记录
            discovery = await self.discovery_crud.get_by_ip(db, ip_address=device.ip_address)

            if discovery:
                if discovery.offline_days >= days_threshold:
                    offline_devices.append(
                        OfflineDevice(
                            device_id=device.id,
                            device_name=device.name,
                            ip_address=device.ip_address,
                            offline_days=discovery.offline_days,
                            last_seen_at=discovery.last_seen_at,
                        )
                    )
            else:
                # 从未扫描到过
                offline_devices.append(
                    OfflineDevice(
                        device_id=device.id,
                        device_name=device.name,
                        ip_address=device.ip_address,
                        offline_days=-1,  # -1 表示从未发现
                        last_seen_at=None,
                    )
                )

        return offline_devices

    async def get_shadow_assets(
        self, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[Discovery], int]:
        """
        获取影子资产列表。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量

        Returns:
            (discoveries, total): 发现记录列表和总数
        """
        return await self.discovery_crud.get_multi_paginated(
            db,
            page=page,
            page_size=page_size,
            status=DiscoveryStatus.SHADOW,
        )

    @transactional()
    async def adopt_device(
        self,
        db: AsyncSession,
        *,
        discovery_id: UUID,
        name: str,
        vendor: str = "other",
        device_group: str = "access",
        dept_id: UUID | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> Device | None:
        """
        纳管设备 (将发现记录转为正式设备)。

        Args:
            db: 数据库会话
            discovery_id: 发现记录ID
            name: 设备名称
            vendor: 厂商
            device_group: 设备分组
            dept_id: 所属部门ID
            username: SSH 用户名
            password: SSH 密码

        Returns:
            创建的 Device 或 None
        """
        from app.core.encryption import encrypt_password
        from app.core.enums import AuthType
        from app.schemas.device import DeviceCreate

        # 获取发现记录
        discovery = await self.discovery_crud.get(db, id=discovery_id)
        if not discovery:
            return None

        # 检查是否已存在同 IP 设备
        existing = await self.device_crud.get_by_ip(db, ip_address=discovery.ip_address)
        if existing:
            # 更新发现记录状态
            await self.discovery_crud.set_matched_device(db, id=discovery_id, device_id=existing.id)
            return existing

        inferred_name = (discovery.snmp_sysname or discovery.hostname or "").strip() or name
        inferred_vendor = (vendor or "").strip() or (discovery.vendor or "").strip() or "other"
        inferred_dept_id = dept_id or getattr(discovery, "dept_id", None)

        # 创建设备（对齐 DeviceService.create_device 的映射逻辑：password -> password_encrypted）
        try:
            vendor_enum = DeviceVendor(inferred_vendor)
        except Exception:
            vendor_enum = DeviceVendor.OTHER

        try:
            group_enum = DeviceGroup(device_group)
        except Exception:
            group_enum = DeviceGroup.ACCESS

        auth_type = AuthType.OTP_MANUAL
        if username and password:
            auth_type = AuthType.STATIC

        os_version = discovery.os_info
        if not os_version and discovery.snmp_sysdescr:
            lines = [s.strip() for s in discovery.snmp_sysdescr.splitlines() if s.strip()]
            if inferred_vendor.lower() == "h3c":
                if lines:
                    os_version = lines[0]
            elif inferred_vendor.lower() == "huawei":
                hit = next((line for line in lines if "version" in line.lower()), None)
                os_version = hit or (lines[0] if lines else None)
            else:
                os_version = lines[0] if lines else None

        stock_in_at = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        device_data = DeviceCreate(
            name=inferred_name,
            ip_address=discovery.ip_address,
            vendor=vendor_enum,
            device_group=group_enum,
            dept_id=inferred_dept_id,
            auth_type=auth_type,
            username=username if auth_type == AuthType.STATIC else None,
            password=password if auth_type == AuthType.STATIC else None,
            ssh_port=22,
            serial_number=getattr(discovery, "serial_number", None),
            os_version=os_version,
            stock_in_at=stock_in_at,
            status=DeviceStatus.IN_USE,
        )

        create_data = device_data.model_dump(exclude={"password"}, exclude_unset=True)
        if device_data.password:
            create_data["password_encrypted"] = encrypt_password(device_data.password)

        device = Device(**create_data)
        db.add(device)
        await db.flush()
        await db.refresh(device)

        # 更新发现记录状态
        await self.discovery_crud.set_matched_device(db, id=discovery_id, device_id=device.id)

        return device
