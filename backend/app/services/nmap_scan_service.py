"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: nmap_scan_service.py
@DateTime: 2026-01-28 10:00:00
@Docs: Nmap/Masscan 网络扫描服务 (Network Scan Service).

专注于网络扫描功能。
"""

import asyncio
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any

import nmap

from app.core.config import settings
from app.core.logger import logger
from app.schemas.discovery import ScanHost, ScanResult


class NmapScanService:
    """
    Nmap/Masscan 网络扫描服务类。

    提供以下功能：
    - Nmap 端口扫描
    - Nmap Ping 存活探测
    - Masscan 快速扫描
    """

    # ========== 扫描工具检测 ==========

    @staticmethod
    def is_nmap_available() -> bool:
        """检查 Nmap 是否可用。"""
        return shutil.which("nmap") is not None

    @staticmethod
    def is_masscan_available() -> bool:
        """检查 Masscan 是否可用。"""
        return shutil.which("masscan") is not None

    def resolve_scan_type(self, scan_type: str) -> str:
        """
        解析扫描类型。

        Args:
            scan_type: 扫描类型（auto/nmap/masscan）

        Returns:
            实际使用的扫描类型
        """
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

    # ========== Nmap 扫描 ==========

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
        """
        使用 Nmap 进行 Ping 存活探测。

        Args:
            subnet: 网段 (CIDR 格式)

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

    def _run_nmap_ping_scan(self, subnet: str) -> list[ScanHost]:
        """运行 Nmap Ping 扫描（同步方法）。"""
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
        """运行 Nmap 扫描（同步方法，在线程池中执行）。"""
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
        """解析 Nmap 扫描结果。"""
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

            # 尝试提取 SSH banner
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

            # vendor 兜底：根据 os_info/ssh_banner 推断
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
                    pass

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

    # ========== Masscan 扫描 ==========

    async def masscan_scan(
        self,
        subnet: str,
        ports: str | None = None,
        rate: int | None = None,
    ) -> ScanResult:
        """
        使用 Masscan 快速扫描网段（仅存活探测）。

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

    def _run_masscan(self, subnet: str, ports: str, rate: int) -> list[ScanHost]:
        """运行 Masscan 扫描（同步方法）。"""
        hosts: list[ScanHost] = []

        try:
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

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.SCAN_TIMEOUT,
            )

            for line in process.stdout.splitlines():
                if line.startswith("Host:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1]
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

    # ========== 辅助方法 ==========

    @staticmethod
    def parse_sysdescr_info(sys_descr: str) -> tuple[str | None, str | None, str | None]:
        """
        解析 SNMP sysDescr 信息。

        Args:
            sys_descr: sysDescr 字符串

        Returns:
            (vendor, model, os_version) 元组
        """
        text = sys_descr.strip()
        if not text:
            return None, None, None

        lines = [s.strip() for s in re.split(r"\r?\n", text) if s and s.strip()]
        if not lines:
            return None, None, None

        vendor = None
        if re.search(r"\bhuawei\b|futurematrix", text, re.IGNORECASE):
            vendor = "huawei"
        elif re.search(r"\bh3c\b|comware", text, re.IGNORECASE):
            vendor = "h3c"

        model = None
        if vendor == "h3c":
            model = lines[1] if len(lines) >= 2 else lines[0]
        elif vendor == "huawei":
            model = lines[0]
        else:
            h3c_line = next((line for line in lines if re.match(r"^h3c\b", line, re.IGNORECASE)), None)
            if h3c_line:
                model = h3c_line
            else:
                huawei_model = next((line for line in lines if re.match(r"^s\d{3,4}-", line, re.IGNORECASE)), None)
                if huawei_model:
                    model = huawei_model
                else:
                    model = lines[0]

        os_version = None
        if vendor == "huawei":
            m = re.search(r"Version\s+([0-9.]+)", text, re.IGNORECASE)
            if m:
                os_version = m.group(1)
        elif vendor == "h3c":
            m = re.search(r"Software\s+Version\s+([0-9.]+)", text, re.IGNORECASE)
            if m:
                os_version = m.group(1)

        return vendor, model, os_version
