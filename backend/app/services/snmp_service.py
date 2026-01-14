"""
@Author: li
@Email: li
@FileName: snmp_service.py
@DateTime: 2026-01-14
@Docs: SNMP v2c 客户端封装。
"""

from collections.abc import Iterable
from dataclasses import dataclass

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    walk_cmd,
)

from app.core.config import settings

SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"
SYS_DESCR_OID = "1.3.6.1.2.1.1.1.0"
ENT_PHYSICAL_SERIAL_OID = "1.3.6.1.2.1.47.1.1.1.1.11"
DOT1D_BASE_BRIDGE_ADDRESS_OID = "1.3.6.1.2.1.17.1.1.0"
IP_AD_ENT_IFINDEX_OID = "1.3.6.1.2.1.4.20.1.2"
IF_PHYS_ADDRESS_OID = "1.3.6.1.2.1.2.2.1.6"
IF_DESCR_OID = "1.3.6.1.2.1.2.2.1.2"


def _to_text(value) -> str:
    try:
        if value is None:
            return ""
        s = str(value)
    except Exception:
        s = ""
    return s.strip()


def _to_bytes(value) -> bytes | None:
    try:
        if hasattr(value, "asOctets"):
            return bytes(value.asOctets())
        return bytes(value)
    except Exception:
        return None


def _format_mac(value) -> str | None:
    b = _to_bytes(value)
    if not b:
        return None
    if len(b) != 6:
        return None
    return ":".join(f"{x:02x}" for x in b)


@dataclass(frozen=True)
class SnmpV2cCredential:
    community: str
    port: int = 161


@dataclass(frozen=True)
class SnmpEnrichResult:
    sys_name: str | None = None
    sys_descr: str | None = None
    serial_number: str | None = None
    bridge_mac: str | None = None
    interface_mac: str | None = None
    interface_name: str | None = None
    ok: bool = False
    error: str | None = None


class SnmpService:
    def __init__(
        self,
        *,
        timeout_seconds: int | None = None,
        retries: int | None = None,
    ):
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.SNMP_TIMEOUT_SECONDS
        self.retries = retries if retries is not None else settings.SNMP_RETRIES

    async def get_many(self, host: str, cred: SnmpV2cCredential, oids: Iterable[str]) -> dict[str, object]:
        oid_list = list(oids)
        engine = SnmpEngine()
        target = await UdpTransportTarget.create(
            (host, cred.port),
            timeout=self.timeout_seconds,
            retries=self.retries,
        )
        community = CommunityData(cred.community, mpModel=1)
        obj_types = [ObjectType(ObjectIdentity(oid)) for oid in oid_list]
        error_indication, error_status, error_index, var_binds = await get_cmd(
            engine,
            community,
            target,
            ContextData(),
            *obj_types,
        )
        if error_indication:
            raise RuntimeError(str(error_indication))
        if error_status:
            idx = int(error_index) - 1 if error_index else -1
            bad_oid = oid_list[idx] if 0 <= idx < len(oid_list) else ""
            raise RuntimeError(f"{str(error_status)} {bad_oid}".strip())

        result: dict[str, object] = {}
        for var_bind in var_binds:
            oid_obj = var_bind[0]
            value = var_bind[1]
            result[str(oid_obj)] = value
        return result

    async def walk(
        self, host: str, cred: SnmpV2cCredential, root_oid: str, *, max_rows: int = 2000
    ) -> list[tuple[str, object]]:
        engine = SnmpEngine()
        target = await UdpTransportTarget.create(
            (host, cred.port),
            timeout=self.timeout_seconds,
            retries=self.retries,
        )
        community = CommunityData(cred.community, mpModel=1)
        rows: list[tuple[str, object]] = []
        async for error_indication, error_status, _, var_binds in walk_cmd(
            engine,
            community,
            target,
            ContextData(),
            ObjectType(ObjectIdentity(root_oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                raise RuntimeError(str(error_indication))
            if error_status:
                raise RuntimeError(str(error_status))
            for var_bind in var_binds:
                oid_obj = var_bind[0]
                value = var_bind[1]
                rows.append((str(oid_obj), value))
                if len(rows) >= max_rows:
                    return rows
        return rows

    async def enrich_basic(self, host: str, cred: SnmpV2cCredential) -> SnmpEnrichResult:
        try:
            values = await self.get_many(host, cred, [SYS_NAME_OID, SYS_DESCR_OID, DOT1D_BASE_BRIDGE_ADDRESS_OID])

            def pick(oid: str):
                if oid in values:
                    return values.get(oid)
                for k, v in values.items():
                    if k.endswith(oid):
                        return v
                return None

            sys_name_value = pick(SYS_NAME_OID)
            sys_descr_value = pick(SYS_DESCR_OID)
            bridge_mac_value = pick(DOT1D_BASE_BRIDGE_ADDRESS_OID)

            sys_name = _to_text(sys_name_value) if sys_name_value is not None else None
            sys_descr = _to_text(sys_descr_value) if sys_descr_value is not None else None
            bridge_mac = _format_mac(bridge_mac_value) if bridge_mac_value is not None else None

            interface_mac = None
            interface_name = None
            try:
                if_index = await self._get_ifindex_by_ip(host, cred)
                if if_index is not None:
                    iface_values = await self.get_many(
                        host,
                        cred,
                        [
                            f"{IF_PHYS_ADDRESS_OID}.{if_index}",
                            f"{IF_DESCR_OID}.{if_index}",
                        ],
                    )
                    iface_mac_value = None
                    iface_descr_value = None
                    for k, v in iface_values.items():
                        if k.endswith(f"{IF_PHYS_ADDRESS_OID}.{if_index}"):
                            iface_mac_value = v
                        if k.endswith(f"{IF_DESCR_OID}.{if_index}"):
                            iface_descr_value = v
                    interface_mac = _format_mac(iface_mac_value) if iface_mac_value is not None else None
                    interface_name = _to_text(iface_descr_value) if iface_descr_value is not None else None
            except Exception:
                interface_mac = None
                interface_name = None

            if not interface_mac:
                try:
                    mac_rows = await self.walk(host, cred, IF_PHYS_ADDRESS_OID, max_rows=2000)
                    mac_candidates: list[str] = []
                    for _, v in mac_rows:
                        m = _format_mac(v)
                        if m and m != "00:00:00:00:00:00":
                            mac_candidates.append(m)
                    if mac_candidates:
                        interface_mac = mac_candidates[0]
                except Exception:
                    interface_mac = None

            serial = None
            try:
                serial_rows = await self.walk(host, cred, ENT_PHYSICAL_SERIAL_OID, max_rows=5000)
                serial_candidates: list[str] = []
                for _, v in serial_rows:
                    s = _to_text(v)
                    if s and s.lower() not in {"none", "null", "unknown", "n/a", "-"}:
                        serial_candidates.append(s)
                if serial_candidates:
                    serial_candidates.sort(key=lambda x: len(x), reverse=True)
                    serial = serial_candidates[0]
            except Exception:
                serial = None

            return SnmpEnrichResult(
                sys_name=sys_name or None,
                sys_descr=sys_descr or None,
                serial_number=serial,
                bridge_mac=bridge_mac,
                interface_mac=interface_mac,
                interface_name=interface_name,
                ok=True,
                error=None,
            )
        except TimeoutError:
            return SnmpEnrichResult(ok=False, error="SNMP 超时")
        except Exception as e:
            return SnmpEnrichResult(ok=False, error=str(e))

    async def _get_ifindex_by_ip(self, ip: str, cred: SnmpV2cCredential) -> int | None:
        parts = ip.split(".")
        if len(parts) != 4:
            return None
        try:
            octets = [int(x) for x in parts]
        except ValueError:
            return None
        if any(x < 0 or x > 255 for x in octets):
            return None

        oid = f"{IP_AD_ENT_IFINDEX_OID}.{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"
        try:
            values = await self.get_many(ip, cred, [oid])
            v = None
            for k, vv in values.items():
                if k.endswith(oid):
                    v = vv
                    break
            if v is None:
                return None
            text = _to_text(v)
            if not text:
                return None
            if "noSuch" in text or "No Such" in text:
                return None
            try:
                return int(text)
            except ValueError:
                return None
        except Exception:
            return None
