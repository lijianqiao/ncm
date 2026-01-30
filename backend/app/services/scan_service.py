"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: scan_service.py
@DateTime: 2026-01-09 23:30:00
@Docs: 网络扫描服务 (Scan Service).

提供 Nmap/Masscan 扫描功能，以及扫描结果与 CMDB 比对。

注意：此文件已重构为组合服务，实际逻辑拆分到：
- nmap_scan_service.py: Nmap/Masscan 扫描功能
- snmp_discovery_service.py: SNMP 发现和 CMDB 比对功能
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_device import CRUDDevice
from app.crud.crud_discovery import CRUDDiscovery
from app.models.device import Device
from app.models.discovery import Discovery
from app.schemas.discovery import (
    CMDBCompareResult,
    OfflineDevice,
    ScanResult,
)
from app.services.nmap_scan_service import NmapScanService
from app.services.snmp_discovery_service import SnmpDiscoveryService


class ScanService:
    """
    网络扫描服务类（组合服务）。

    此类组合了 NmapScanService 和 SnmpDiscoveryService，
    保持向后兼容性。

    推荐直接使用拆分后的服务类：
    - NmapScanService: 网络扫描功能
    - SnmpDiscoveryService: SNMP 发现和 CMDB 比对
    """

    def __init__(
        self,
        discovery_crud: CRUDDiscovery,
        device_crud: CRUDDevice,
    ):
        """
        初始化网络扫描服务。

        Args:
            discovery_crud: 发现记录 CRUD 实例
            device_crud: 设备 CRUD 实例
        """
        self.discovery_crud = discovery_crud
        self.device_crud = device_crud
        # 组合子服务
        self._nmap_service = NmapScanService()
        self._snmp_discovery_service = SnmpDiscoveryService(discovery_crud, device_crud)

    # ========== 扫描工具检测（委托给 NmapScanService）==========

    def is_nmap_available(self) -> bool:
        return self._nmap_service.is_nmap_available()

    def is_masscan_available(self) -> bool:
        return self._nmap_service.is_masscan_available()

    def resolve_scan_type(self, scan_type: str) -> str:
        return self._nmap_service.resolve_scan_type(scan_type)

    # ========== Nmap/Masscan 扫描（委托给 NmapScanService）==========

    async def nmap_scan(
        self,
        subnet: str,
        ports: str | None = None,
        arguments: str = "-sS -sV -O --host-timeout 30s",
    ) -> ScanResult:
        return await self._nmap_service.nmap_scan(subnet, ports, arguments)

    async def nmap_ping_scan(self, subnet: str) -> ScanResult:
        return await self._nmap_service.nmap_ping_scan(subnet)

    async def masscan_scan(
        self,
        subnet: str,
        ports: str | None = None,
        rate: int | None = None,
    ) -> ScanResult:
        return await self._nmap_service.masscan_scan(subnet, ports, rate)

    # ========== 扫描结果处理（委托给 SnmpDiscoveryService）==========

    async def process_scan_result(
        self,
        db: AsyncSession,
        scan_result: ScanResult,
        scan_task_id: str | None = None,
        snmp_cred_id: UUID | None = None,
    ) -> int:
        return await self._snmp_discovery_service.process_scan_result(
            db, scan_result, scan_task_id, snmp_cred_id
        )

    # ========== CMDB 比对（委托给 SnmpDiscoveryService）==========

    async def compare_with_cmdb(self, db: AsyncSession) -> CMDBCompareResult:
        return await self._snmp_discovery_service.compare_with_cmdb(db)

    async def detect_offline_devices(self, db: AsyncSession, days_threshold: int = 7) -> list[OfflineDevice]:
        return await self._snmp_discovery_service.detect_offline_devices(db, days_threshold)

    async def get_shadow_assets(
        self, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[Discovery], int]:
        return await self._snmp_discovery_service.get_shadow_assets(db, page, page_size)

    # ========== 设备纳管（委托给 SnmpDiscoveryService）==========

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
        return await self._snmp_discovery_service.adopt_device(
            db,
            discovery_id=discovery_id,
            name=name,
            vendor=vendor,
            device_group=device_group,
            dept_id=dept_id,
            username=username,
            password=password,
        )

    # ========== 保留的辅助方法（用于兼容性）==========

    def _parse_sysdescr_info(self, sys_descr: str) -> tuple[str | None, str | None, str | None]:
        """解析 SNMP sysDescr 信息（已移至 NmapScanService）。"""
        return NmapScanService.parse_sysdescr_info(sys_descr)
