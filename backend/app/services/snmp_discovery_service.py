"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: snmp_discovery_service.py
@DateTime: 2026-01-28 10:00:00
@Docs: SNMP 设备发现服务 (SNMP Discovery Service).

专注于 SNMP 设备发现和 CMDB 比对功能。
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decorator import transactional
from app.core.encryption import decrypt_snmp_secret, encrypt_password
from app.core.enums import AuthType, DeviceGroup, DeviceStatus, DeviceVendor, DiscoveryStatus
from app.core.logger import logger
from app.crud.crud_device import CRUDDevice
from app.crud.crud_discovery import CRUDDiscovery
from app.crud.crud_snmp_credential import dept_snmp_credential as dept_snmp_credential_crud
from app.models.device import Device
from app.models.discovery import Discovery
from app.schemas.device import DeviceCreate
from app.schemas.discovery import (
    CMDBCompareResult,
    DiscoveryCreate,
    OfflineDevice,
    ScanResult,
)
from app.services.nmap_scan_service import NmapScanService
from app.services.snmp_service import SnmpService, SnmpV2cCredential


class SnmpDiscoveryService:
    """
    SNMP 设备发现服务类。

    提供以下功能：
    - 处理扫描结果并进行 SNMP 补全
    - 与 CMDB 比对
    - 检测离线设备
    - 获取影子资产
    - 设备纳管
    """

    def __init__(
        self,
        discovery_crud: CRUDDiscovery,
        device_crud: CRUDDevice,
    ):
        self.discovery_crud = discovery_crud
        self.device_crud = device_crud

    # ========== 扫描结果处理 ==========

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
            snmp_cred_id: SNMP 凭据ID（用于 SNMP 补全）

        Returns:
            处理的主机数量
        """
        # SNMP 补全
        snmp_results = await self._enrich_with_snmp(db, scan_result, snmp_cred_id)

        # 构建发现数据
        data_list = self._build_discovery_data(scan_result, snmp_results, scan_task_id)

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

    async def _enrich_with_snmp(
        self,
        db: AsyncSession,
        scan_result: ScanResult,
        snmp_cred_id: UUID | None,
    ) -> dict[str, dict[str, Any]]:
        """使用 SNMP 补全扫描结果。"""
        snmp_results: dict[str, dict[str, Any]] = {}

        if not snmp_cred_id:
            return snmp_results

        try:
            snmp_cred = await dept_snmp_credential_crud.get(db, id=snmp_cred_id)
            if not snmp_cred or snmp_cred.is_deleted:
                return snmp_results

            if snmp_cred.snmp_version != "v2c" or not snmp_cred.community_encrypted:
                logger.warning("SNMP 凭据不可用或不支持 v2c", snmp_cred_id=str(snmp_cred_id))
                return snmp_results

            community = decrypt_snmp_secret(snmp_cred.community_encrypted)
            snmp_service = SnmpService()
            cred = SnmpV2cCredential(community=community, port=snmp_cred.port)
            sem = asyncio.Semaphore(settings.SNMP_MAX_CONCURRENCY)

            async def _enrich(ip: str) -> tuple[str, dict[str, Any] | None]:
                async with sem:
                    r = await snmp_service.enrich_basic(ip, cred)
                    if r is None:
                        return ip, None
                    return ip, {
                        "snmp_sysname": r.sys_name,
                        "snmp_sysdescr": r.sys_descr,
                        "serial_number": r.serial_number,
                        "bridge_mac": r.bridge_mac,
                        "interface_mac": r.interface_mac,
                        "interface_name": r.interface_name,
                        "snmp_ok": r.ok,
                        "snmp_error": r.error,
                    }

            tasks = [_enrich(h.ip_address) for h in scan_result.hosts]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for item in results:
                if isinstance(item, BaseException):
                    continue
                if isinstance(item, tuple):
                    ip, data = item
                    if data:
                        snmp_results[ip] = data

        except Exception as e:
            logger.warning("SNMP 补全失败（已忽略，不影响扫描入库）", error=str(e))

        return snmp_results

    def _build_discovery_data(
        self,
        scan_result: ScanResult,
        snmp_results: dict[str, dict[str, Any]],
        scan_task_id: str | None,
    ) -> list[DiscoveryCreate]:
        """构建发现数据列表。"""
        data_list: list[DiscoveryCreate] = []

        for host in scan_result.hosts:
            try:
                snmp_data = snmp_results.get(host.ip_address, {})
                sys_descr = snmp_data.get("snmp_sysdescr")
                sys_name = snmp_data.get("snmp_sysname")

                inferred_vendor = None
                inferred_model = None
                inferred_version = None
                if isinstance(sys_descr, str) and sys_descr:
                    inferred_vendor, inferred_model, inferred_version = NmapScanService.parse_sysdescr_info(sys_descr)

                mac_address = host.mac_address or snmp_data.get("interface_mac") or snmp_data.get("bridge_mac")

                data_list.append(
                    DiscoveryCreate(
                        ip_address=host.ip_address,
                        mac_address=mac_address,
                        vendor=inferred_vendor,
                        device_type=inferred_model,
                        hostname=(sys_name if isinstance(sys_name, str) and sys_name else None) or host.hostname,
                        os_info=inferred_version,
                        serial_number=snmp_data.get("serial_number"),
                        open_ports=host.open_ports,
                        ssh_banner=getattr(host, "ssh_banner", None),
                        scan_source=scan_result.scan_type,
                        scan_task_id=scan_task_id,
                        snmp_sysname=snmp_data.get("snmp_sysname"),
                        snmp_sysdescr=snmp_data.get("snmp_sysdescr"),
                        snmp_ok=snmp_data.get("snmp_ok"),
                        snmp_error=snmp_data.get("snmp_error"),
                    )
                )
            except Exception as e:
                logger.error(f"构造发现数据失败: {host.ip_address}", error=str(e))

        return data_list

    # ========== CMDB 比对 ==========

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
        discoveries, total_discovered = await self.discovery_crud.get_paginated(
            db, page=1, page_size=10000, max_size=10000
        )
        result.total_discovered = total_discovered

        # 获取所有设备
        devices, total_cmdb = await self.device_crud.get_paginated(db, page=1, page_size=10000, max_size=10000)
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
        offline_count = sum(1 for device in devices if device.ip_address not in discovered_ips)
        result.offline_devices = offline_count

        return result

    # ========== 离线设备检测 ==========

    async def detect_offline_devices(self, db: AsyncSession, days_threshold: int = 7) -> list[OfflineDevice]:
        """
        检测离线设备（CMDB 中存在但长时间未扫描到）。

        Args:
            db: 数据库会话
            days_threshold: 离线天数阈值

        Returns:
            OfflineDevice 列表
        """
        offline_devices: list[OfflineDevice] = []

        # 获取所有活跃设备
        devices, _ = await self.device_crud.get_paginated(
            db, page=1, page_size=10000, max_size=10000, status=DeviceStatus.ACTIVE.value
        )

        for device in devices:
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

    # ========== 影子资产 ==========

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
        return await self.discovery_crud.get_paginated(
            db,
            page=page,
            page_size=page_size,
            max_size=10000,
            status=DiscoveryStatus.SHADOW.value,
        )

    # ========== 设备纳管 ==========

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
        纳管设备（将发现记录转为正式设备）。

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
        # 获取发现记录
        discovery = await self.discovery_crud.get(db, id=discovery_id)
        if not discovery:
            return None

        # 检查是否已存在同 IP 设备
        existing = await self.device_crud.get_by_ip(db, ip_address=discovery.ip_address)
        if existing:
            await self.discovery_crud.set_matched_device(db, id=discovery_id, device_id=existing.id)
            return existing

        # 推断字段值
        inferred_name = (discovery.snmp_sysname or discovery.hostname or "").strip() or name
        inferred_vendor = (vendor or "").strip() or (discovery.vendor or "").strip() or "other"
        inferred_dept_id = dept_id or getattr(discovery, "dept_id", None)

        # 解析枚举
        try:
            vendor_enum = DeviceVendor(inferred_vendor)
        except Exception:
            vendor_enum = DeviceVendor.OTHER

        try:
            group_enum = DeviceGroup(device_group)
        except Exception:
            group_enum = DeviceGroup.ACCESS

        # 确定认证类型
        auth_type = AuthType.OTP_MANUAL
        if username and password:
            auth_type = AuthType.STATIC

        # 解析 OS 版本
        os_version = discovery.os_info
        if not os_version and discovery.snmp_sysdescr:
            lines = [s.strip() for s in discovery.snmp_sysdescr.splitlines() if s.strip()]
            if inferred_vendor.lower() == "h3c":
                os_version = lines[0] if lines else None
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
            model=getattr(discovery, "device_type", None),
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
