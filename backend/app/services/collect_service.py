"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: collect_service.py
@DateTime: 2026-01-09 22:10:00
@Docs: ARP/MAC 采集服务 (Collection Service).

负责从网络设备采集 ARP/MAC 表数据，并缓存到 Redis。
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from scrapli import Scrapli
from scrapli.exceptions import ScrapliAuthenticationFailed
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache as cache_module
from app.core.config import settings
from app.core.enums import AuthType, DeviceStatus
from app.core.exceptions import BadRequestException, NotFoundException, OTPRequiredException
from app.core.logger import logger
from app.core.otp_service import otp_service
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.models.device import Device
from app.network.platform_config import get_command, get_platform_for_vendor, get_scrapli_options
from app.network.textfsm_parser import parse_arp_table, parse_mac_table
from app.schemas.collect import (
    ARPEntry,
    ARPTableResponse,
    CollectBatchRequest,
    CollectResult,
    DeviceCollectResult,
    LocateMatch,
    LocateResponse,
    MACEntry,
    MACTableResponse,
)

# Redis 键前缀
ARP_CACHE_PREFIX = "ncm:arp"
MAC_CACHE_PREFIX = "ncm:mac"
COLLECT_LAST_PREFIX = "ncm:collect:last"


class CollectService:
    """
    ARP/MAC 采集服务类。
    """

    def __init__(self, db: AsyncSession, device_crud: CRUDDevice, credential_crud: CRUDCredential):
        self.db = db
        self.device_crud = device_crud
        self.credential_crud = credential_crud

    # ===== 缓存查询 =====

    async def get_cached_arp(self, device_id: UUID) -> ARPTableResponse:
        """
        获取设备缓存的 ARP 表。

        Args:
            device_id: 设备ID

        Returns:
            ARPTableResponse: ARP 表响应

        Raises:
            NotFoundException: 设备不存在
        """
        # 验证设备存在
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        entries: list[ARPEntry] = []
        cached_at: datetime | None = None

        if cache_module.redis_client:
            cache_key = f"{ARP_CACHE_PREFIX}:{device_id}"
            try:
                cached_data = await cache_module.redis_client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    entries = [ARPEntry(**entry) for entry in data.get("entries", [])]
                    cached_at = datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None
            except Exception as e:
                logger.warning(f"读取 ARP 缓存失败: {e}")

        return ARPTableResponse(
            device_id=device_id,
            device_name=device.name,
            entries=entries,
            total=len(entries),
            cached_at=cached_at,
        )

    async def get_cached_mac(self, device_id: UUID) -> MACTableResponse:
        """
        获取设备缓存的 MAC 表。

        Args:
            device_id: 设备ID

        Returns:
            MACTableResponse: MAC 表响应

        Raises:
            NotFoundException: 设备不存在
        """
        # 验证设备存在
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        entries: list[MACEntry] = []
        cached_at: datetime | None = None

        if cache_module.redis_client:
            cache_key = f"{MAC_CACHE_PREFIX}:{device_id}"
            try:
                cached_data = await cache_module.redis_client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    entries = [MACEntry(**entry) for entry in data.get("entries", [])]
                    cached_at = datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None
            except Exception as e:
                logger.warning(f"读取 MAC 缓存失败: {e}")

        return MACTableResponse(
            device_id=device_id,
            device_name=device.name,
            entries=entries,
            total=len(entries),
            cached_at=cached_at,
        )

    # ===== 单设备采集 =====

    async def collect_device(
        self,
        device_id: UUID,
        collect_arp: bool = True,
        collect_mac: bool = True,
        otp_code: str | None = None,
    ) -> DeviceCollectResult:
        """
        采集单设备的 ARP/MAC 表。

        Args:
            device_id: 设备ID
            collect_arp: 是否采集 ARP
            collect_mac: 是否采集 MAC
            otp_code: OTP 验证码（如果设备需要）

        Returns:
            DeviceCollectResult: 采集结果
        """
        start_time = time.time()

        # 获取设备信息
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            return DeviceCollectResult(
                device_id=device_id,
                success=False,
                error_message="设备不存在",
            )

        if device.status != DeviceStatus.ACTIVE:
            return DeviceCollectResult(
                device_id=device_id,
                device_name=device.name,
                success=False,
                error_message=f"设备状态异常 {device.status}",
            )

        # 获取凭据
        try:
            credential = await self._get_device_credential(device, otp_code)
        except OTPRequiredException:
            raise
        except Exception as e:
            logger.warning(
                f"获取凭据失败: device={device.name}, auth_type={device.auth_type}, error={e}",
                exc_info=True,
            )
            return DeviceCollectResult(
                device_id=device_id,
                device_name=device.name,
                success=False,
                error_message=f"获取凭据失败: {str(e)}",
            )

        # 连接设备并采集
        platform = get_platform_for_vendor(device.vendor if device.vendor else "h3c")
        scrapli_options = get_scrapli_options(platform)

        device_config = {
            "host": device.ip_address,
            "auth_username": credential["username"],
            "auth_password": credential["password"],
            "port": device.ssh_port or 22,
            "platform": platform,
            **scrapli_options,
        }

        arp_count = 0
        mac_count = 0

        try:

            def _sync_collect() -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
                with Scrapli(**device_config) as conn:
                    arp_entries_out = None
                    mac_entries_out = None

                    if collect_arp:
                        arp_cmd = get_command("arp_table", platform)
                        arp_response = conn.send_command(arp_cmd, timeout_ops=120)
                        if arp_response.failed:
                            raise RuntimeError(str(arp_response.result))
                        arp_entries_out = parse_arp_table(platform, arp_response.result)

                    if collect_mac:
                        mac_cmd = get_command("mac_table", platform)
                        mac_response = conn.send_command(mac_cmd, timeout_ops=120)
                        if mac_response.failed:
                            raise RuntimeError(str(mac_response.result))
                        mac_entries_out = parse_mac_table(platform, mac_response.result)

                    return arp_entries_out, mac_entries_out

            arp_entries, mac_entries = await asyncio.to_thread(_sync_collect)
            if arp_entries is not None:
                await self._save_arp_cache(device_id, arp_entries)
                arp_count = len(arp_entries)
                logger.debug(f"ARP 采集成功: device={device.name}, entries={arp_count}")
            if mac_entries is not None:
                await self._save_mac_cache(device_id, mac_entries)
                mac_count = len(mac_entries)
                logger.debug(f"MAC 采集成功: device={device.name}, entries={mac_count}")

            await self._update_last_collect_time(device_id)

        except ScrapliAuthenticationFailed as e:
            # 单独处理认证失败，尝试触发 OTP 流程
            from app.network.otp_utils import handle_otp_auth_failure

            duration_ms = int((time.time() - start_time) * 1000)

            logger.warning(f"捕获 ScrapliAuthenticationFailed: {e}")

            host_data = {
                "auth_type": device.auth_type,
                "dept_id": str(device.dept_id) if device.dept_id else None,
                "device_group": device.device_group,
                "device_id": str(device.id),
                "name": device.name,
            }
            await handle_otp_auth_failure(host_data, e)

            return DeviceCollectResult(
                device_id=device_id,
                device_name=device.name,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"采集失败: device={device.name}, error={str(e)}, type={type(e)}")

            # Fallback: 检查字符串是否包含认证失败信息
            error_str = str(e).lower()
            if "authentication" in error_str and (
                "failed" in error_str or "refused" in error_str or "method" in error_str
            ):
                try:
                    from app.network.otp_utils import handle_otp_auth_failure

                    logger.warning(f"通过错误信息检测到认证失败 (Fallback): {e}")
                    host_data = {
                        "auth_type": device.auth_type,
                        "dept_id": str(device.dept_id) if device.dept_id else None,
                        "device_group": device.device_group,
                        "device_id": str(device.id),
                        "name": device.name,
                    }
                    await handle_otp_auth_failure(host_data, e)
                except OTPRequiredException:
                    raise
                except Exception as fallback_e:
                    logger.warning(f"Fallback OTP handling failed: {fallback_e}")

            return DeviceCollectResult(
                device_id=device_id,
                device_name=device.name,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
            )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"采集完成: device={device.name}, arp={arp_count}, mac={mac_count}, duration={duration_ms}ms")

        return DeviceCollectResult(
            device_id=device_id,
            device_name=device.name,
            success=True,
            arp_count=arp_count,
            mac_count=mac_count,
            duration_ms=duration_ms,
        )

    # ===== 批量采集 =====

    async def batch_collect(
        self,
        request: CollectBatchRequest,
        concurrency: int = 10,
    ) -> CollectResult:
        """
        批量采集多台设备的 ARP/MAC 表。

        Args:
            request: 批量采集请求
            concurrency: 并发数
        Returns:
            CollectResult: 采集结果
        """
        started_at = datetime.now()
        semaphore = asyncio.Semaphore(concurrency)

        # 如果提供了 OTP，先缓存
        if request.otp_code:
            # 获取设备列表确定需要缓存 OTP 的部分设备
            devices = await self.device_crud.get_by_ids(self.db, request.device_ids, options=self.device_crud._DEVICE_OPTIONS)
            for device in devices:
                auth_type_str = device.auth_type or AuthType.STATIC.value
                try:
                    auth_type = AuthType(auth_type_str)
                except ValueError:
                    auth_type = AuthType.STATIC
                if auth_type == AuthType.OTP_MANUAL and device.dept_id and device.device_group:
                    await otp_service.cache_otp(device.dept_id, device.device_group, request.otp_code)

        async def collect_with_semaphore(device_id: UUID) -> DeviceCollectResult:
            async with semaphore:
                return await self.collect_device(
                    device_id=device_id,
                    collect_arp=request.collect_arp,
                    collect_mac=request.collect_mac,
                )

        tasks = [collect_with_semaphore(device_id) for device_id in request.device_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        device_results: list[DeviceCollectResult] = []
        success_count = 0
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_results.append(
                    DeviceCollectResult(
                        device_id=request.device_ids[i],
                        success=False,
                        error_message=str(result),
                    )
                )
                failed_count += 1
            elif isinstance(result, DeviceCollectResult):
                device_results.append(result)
                if result.success:
                    success_count += 1
                else:
                    failed_count += 1

        completed_at = datetime.now()
        logger.info(f"批量采集完成: total={len(request.device_ids)}, success={success_count}, failed={failed_count}")

        return CollectResult(
            total_devices=len(request.device_ids),
            success_count=success_count,
            failed_count=failed_count,
            results=device_results,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def collect_all_active_devices(
        self,
        collect_arp: bool = True,
        collect_mac: bool = True,
        concurrency: int = 10,
    ) -> CollectResult:
        """
        采集所有活跃设备的 ARP/MAC 表（用于定时任务）。

        Args:
            collect_arp: 是否采集 ARP
            collect_mac: 是否采集 MAC
            concurrency: 并发数

        Returns:
            CollectResult: 采集结果
        """
        # 获取所有活跃设备
        devices, _ = await self.device_crud.get_paginated(
            self.db,
            page=1,
            page_size=10000,
            max_size=10000,
            status=DeviceStatus.ACTIVE.value,
        )

        if not devices:
            logger.info("没有活跃设备，跳过采集")
            return CollectResult(total_devices=0)

        device_ids = [device.id for device in devices]
        request = CollectBatchRequest(
            device_ids=device_ids,
            collect_arp=collect_arp,
            collect_mac=collect_mac,
        )

        return await self.batch_collect(request, concurrency=concurrency)

    # ===== 内部方法 =====

    async def _get_device_credential(self, device: Device, otp_code: str | None = None) -> dict[str, str]:
        """
        获取设备连接凭据。

        Returns:
            dict: {"username": str, "password": str}
        """
        auth_type_str = device.auth_type or AuthType.STATIC.value
        # 将字符串转换为枚 AuthType 枚举
        try:
            auth_type = AuthType(auth_type_str)
        except ValueError:
            auth_type = AuthType.STATIC

        if auth_type == AuthType.STATIC:
            # 静态密码
            if not device.username:
                raise BadRequestException(message="设备未配置用户名")
            if not device.password_encrypted:
                raise BadRequestException(message="设备未配置密码")
            from app.core.encryption import decrypt_password

            password = decrypt_password(device.password_encrypted)
            return {"username": device.username, "password": password}

        elif auth_type == AuthType.OTP_SEED:
            # 自动生成 OTP - 从 DeviceGroupCredential 获取种子
            if not device.dept_id or not device.device_group:
                raise BadRequestException(message="OTP_SEED 认证需要配置部门和设备组")

            group_credential = await self.credential_crud.get_by_dept_and_group(
                self.db, device.dept_id, device.device_group
            )
            if not group_credential:
                raise BadRequestException(message="未找到凭据配置")
            if not group_credential.username:
                raise BadRequestException(message="凭据未配置用户名")
            if not group_credential.otp_seed_encrypted:
                raise BadRequestException(message="凭据未配置 OTP 种子")

            device_credential = await otp_service.get_credential_for_otp_seed_device(
                username=group_credential.username,
                encrypted_seed=group_credential.otp_seed_encrypted,
            )
            return {"username": device_credential.username, "password": device_credential.password}

        elif auth_type == AuthType.OTP_MANUAL:
            # 手动输入 OTP
            if otp_code and device.dept_id and device.device_group:
                # 缓存提供的 OTP
                ttl = await otp_service.cache_otp(device.dept_id, device.device_group, otp_code)
                if ttl == 0:
                    raise BadRequestException(message="OTP 缓存失败：Redis 服务未连接，请联系管理员")

            if not device.dept_id or not device.device_group:
                raise BadRequestException(message="设备未配置部门或设备组")

            group_credential = await self.credential_crud.get_by_dept_and_group(
                self.db, device.dept_id, device.device_group
            )
            if not group_credential:
                raise BadRequestException(message="未找到凭据配置")
            if not group_credential.username:
                raise BadRequestException(message="凭据未配置用户名")

            device_credential = await otp_service.get_credential_for_otp_manual_device(
                username=group_credential.username,
                dept_id=device.dept_id,
                device_group=device.device_group,
                failed_devices=[str(device.id)],
            )
            return {"username": device_credential.username, "password": device_credential.password}

        else:
            raise BadRequestException(message=f"不支持的认证类型: {auth_type}")

    async def _save_arp_cache(self, device_id: UUID, entries: list[dict[str, Any]]) -> None:
        """保存 ARP 表到 Redis 缓存。"""
        if not cache_module.redis_client:
            return

        cache_key = f"{ARP_CACHE_PREFIX}:{device_id}"
        now = datetime.now()

        # 规范化条目
        normalized_entries = []
        for entry in entries:
            normalized_entries.append(
                {
                    "ip_address": entry.get("ip_address", entry.get("address", "")),
                    "mac_address": entry.get("mac_address", entry.get("mac", "")),
                    "vlan_id": entry.get("vlan_id", entry.get("vlan", "")),
                    "interface": entry.get("interface", entry.get("port", "")),
                    "age": entry.get("age", entry.get("aging", "")),
                    "entry_type": entry.get("type", entry.get("entry_type", "")),
                    "updated_at": now.isoformat(),
                }
            )

        cache_data = {
            "entries": normalized_entries,
            "cached_at": now.isoformat(),
        }

        try:
            await cache_module.redis_client.setex(
                cache_key,
                settings.COLLECT_CACHE_TTL,
                json.dumps(cache_data),
            )
        except Exception as e:
            logger.warning(f"保存 ARP 缓存失败: {e}")

    async def _save_mac_cache(self, device_id: UUID, entries: list[dict[str, Any]]) -> None:
        """保存 MAC 表到 Redis 缓存。"""
        if not cache_module.redis_client:
            return

        cache_key = f"{MAC_CACHE_PREFIX}:{device_id}"
        now = datetime.now()

        # 规范化条目
        normalized_entries = []
        for entry in entries:
            normalized_entries.append(
                {
                    "mac_address": entry.get("mac_address", entry.get("destination_address", entry.get("mac", ""))),
                    "vlan_id": entry.get("vlan_id", entry.get("vlan", "")),
                    "interface": entry.get("interface", entry.get("port", entry.get("destination_port", ""))),
                    "entry_type": entry.get("type", entry.get("entry_type", "")),
                    "state": entry.get("state", ""),
                    "updated_at": now.isoformat(),
                }
            )

        cache_data = {
            "entries": normalized_entries,
            "cached_at": now.isoformat(),
        }

        try:
            await cache_module.redis_client.setex(
                cache_key,
                settings.COLLECT_CACHE_TTL,
                json.dumps(cache_data),
            )
        except Exception as e:
            logger.warning(f"保存 MAC 缓存失败: {e}")

    async def _update_last_collect_time(self, device_id: UUID) -> None:
        """更新设备最后采集时间。"""
        if not cache_module.redis_client:
            return

        cache_key = f"{COLLECT_LAST_PREFIX}:{device_id}"
        try:
            await cache_module.redis_client.setex(
                cache_key,
                settings.COLLECT_CACHE_TTL * 2,  # 保留更长时间
                datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"更新最后采集时间失败 {e}")

    # ===== IP/MAC 精准定位 =====

    async def locate_by_ip(self, ip_address: str) -> LocateResponse:
        """
        根据 IP 地址定位设备和端口

        遍历所有设备的 ARP 缓存，查找匹配的 IP 地址

        Args:
            ip_address: 要查询的 IP 地址

        Returns:
            LocateResponse: 定位结果
        """
        start_time = time.time()
        matches: list[LocateMatch] = []
        searched_devices = 0

        if not cache_module.redis_client:
            logger.warning("Redis 未连接，无法执行定位查询")
            return LocateResponse(
                query=ip_address,
                query_type="ip",
                matches=[],
                total=0,
                searched_devices=0,
                search_time_ms=0,
            )

        # 获取所有设备
        devices, _ = await self.device_crud.get_paginated(
            self.db,
            page=1,
            page_size=10000,
            max_size=10000,
        )

        # 预加载设备信息映射
        device_map = {str(d.id): d for d in devices}

        # 扫描所有 ARP 缓存
        try:
            async for key in cache_module.redis_client.scan_iter(match=f"{ARP_CACHE_PREFIX}:*"):
                searched_devices += 1
                device_id = key.split(":")[-1]
                device = device_map.get(device_id)

                cached_data = await cache_module.redis_client.get(key)
                if not cached_data:
                    continue

                data = json.loads(cached_data)
                entries = data.get("entries", [])
                cached_at = datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None

                # 搜索匹配 IP
                for entry in entries:
                    if entry.get("ip_address", "").lower() == ip_address.lower():
                        matches.append(
                            LocateMatch(
                                device_id=UUID(device_id),
                                device_name=device.name if device else None,
                                device_ip=device.ip_address if device else None,
                                interface=entry.get("interface"),
                                vlan_id=entry.get("vlan_id"),
                                mac_address=entry.get("mac_address"),
                                entry_type=entry.get("entry_type"),
                                cached_at=cached_at,
                            )
                        )

        except Exception as e:
            logger.error(f"IP 定位查询失败: {e}")

        search_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"IP 定位完成: query={ip_address}, matches={len(matches)}, "
            f"devices={searched_devices}, time={search_time_ms}ms"
        )

        return LocateResponse(
            query=ip_address,
            query_type="ip",
            matches=matches,
            total=len(matches),
            searched_devices=searched_devices,
            search_time_ms=search_time_ms,
        )

    async def locate_by_mac(self, mac_address: str) -> LocateResponse:
        """
        根据 MAC 地址定位设备和端口

        同时搜索 ARP 和 MAC 缓存，合并结果

        Args:
            mac_address: 要查询的 MAC 地址

        Returns:
            LocateResponse: 定位结果
        """
        start_time = time.time()
        matches: list[LocateMatch] = []
        searched_devices = 0

        if not cache_module.redis_client:
            logger.warning("Redis 未连接，无法执行定位查询")
            return LocateResponse(
                query=mac_address,
                query_type="mac",
                matches=[],
                total=0,
                searched_devices=0,
                search_time_ms=0,
            )

        # 标准化 MAC 地址格式（支持多种格式搜索）
        mac_normalized = mac_address.lower().replace("-", "").replace(":", "").replace(".", "")

        def mac_matches(stored_mac: str) -> bool:
            """检查 MAC 是否匹配（忽略分隔符格式差异）。"""
            if not stored_mac:
                return False
            stored_normalized = stored_mac.lower().replace("-", "").replace(":", "").replace(".", "")
            return stored_normalized == mac_normalized

        # 获取所有设备
        devices, _ = await self.device_crud.get_paginated(
            self.db,
            page=1,
            page_size=10000,
            max_size=10000,
        )

        # 预加载设备信息映射
        device_map = {str(d.id): d for d in devices}

        # 用于去重的集合（device_id + interface）
        found_locations: set[str] = set()

        try:
            # 1. 搜索 ARP 缓存（可获取 IP 地址）
            async for key in cache_module.redis_client.scan_iter(match=f"{ARP_CACHE_PREFIX}:*"):
                searched_devices += 1
                device_id = key.split(":")[-1]
                device = device_map.get(device_id)

                cached_data = await cache_module.redis_client.get(key)
                if not cached_data:
                    continue

                data = json.loads(cached_data)
                entries = data.get("entries", [])
                cached_at = datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None

                for entry in entries:
                    if mac_matches(entry.get("mac_address", "")):
                        location_key = f"{device_id}:{entry.get('interface', '')}"
                        if location_key not in found_locations:
                            found_locations.add(location_key)
                            matches.append(
                                LocateMatch(
                                    device_id=UUID(device_id),
                                    device_name=device.name if device else None,
                                    device_ip=device.ip_address if device else None,
                                    interface=entry.get("interface"),
                                    vlan_id=entry.get("vlan_id"),
                                    ip_address=entry.get("ip_address"),
                                    mac_address=entry.get("mac_address"),
                                    entry_type=entry.get("entry_type"),
                                    cached_at=cached_at,
                                )
                            )

            # 2. 搜索 MAC 缓存（可能有更精确的端口信息）
            async for key in cache_module.redis_client.scan_iter(match=f"{MAC_CACHE_PREFIX}:*"):
                device_id = key.split(":")[-1]
                device = device_map.get(device_id)

                cached_data = await cache_module.redis_client.get(key)
                if not cached_data:
                    continue

                data = json.loads(cached_data)
                entries = data.get("entries", [])
                cached_at = datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None

                for entry in entries:
                    if mac_matches(entry.get("mac_address", "")):
                        location_key = f"{device_id}:{entry.get('interface', '')}"
                        if location_key not in found_locations:
                            found_locations.add(location_key)
                            matches.append(
                                LocateMatch(
                                    device_id=UUID(device_id),
                                    device_name=device.name if device else None,
                                    device_ip=device.ip_address if device else None,
                                    interface=entry.get("interface"),
                                    vlan_id=entry.get("vlan_id"),
                                    mac_address=entry.get("mac_address"),
                                    entry_type=entry.get("entry_type") or entry.get("state"),
                                    cached_at=cached_at,
                                )
                            )

        except Exception as e:
            logger.error(f"MAC 定位查询失败: {e}")

        search_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"MAC 定位完成: query={mac_address}, matches={len(matches)}, "
            f"devices={searched_devices}, time={search_time_ms}ms"
        )

        return LocateResponse(
            query=mac_address,
            query_type="mac",
            matches=matches,
            total=len(matches),
            searched_devices=searched_devices,
            search_time_ms=search_time_ms,
        )
