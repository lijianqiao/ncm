"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: platform_config.py
@DateTime: 2026-01-09 18:00:00
@Docs: 网络设备平台配置 (Network Device Platform Configuration).

集中管理厂商、平台、命令映射关系，支持多厂商统一接口调用。
"""

from enum import Enum
from typing import Any


class VendorType(str, Enum):
    """设备厂商类型枚举。

    Attributes:
        H3C: H3C 厂商
        HUAWEI: 华为厂商
        CISCO: 思科厂商
        ARISTA: Arista 厂商
        JUNIPER: Juniper 厂商
    """

    H3C = "h3c"
    HUAWEI = "huawei"
    CISCO = "cisco"
    ARISTA = "arista"
    JUNIPER = "juniper"


class ScrapliPlatform(str, Enum):
    """Scrapli 平台标识枚举。

    Attributes:
        HP_COMWARE: H3C Comware 平台
        HUAWEI_VRP: 华为 VRP 平台
        CISCO_IOSXE: 思科 IOS XE 平台
        CISCO_NXOS: 思科 NX-OS 平台
        ARISTA_EOS: Arista EOS 平台
        JUNIPER_JUNOS: Juniper JunOS 平台
    """

    HP_COMWARE = "hp_comware"
    HUAWEI_VRP = "huawei_vrp"
    CISCO_IOSXE = "cisco_iosxe"
    CISCO_NXOS = "cisco_nxos"
    ARISTA_EOS = "arista_eos"
    JUNIPER_JUNOS = "juniper_junos"


# ===== 厂商 → Scrapli 平台映射 =====
VENDOR_PLATFORM_MAP: dict[str, str] = {
    "h3c": "hp_comware",
    "huawei": "huawei_vrp",
    "cisco": "cisco_iosxe",
    "arista": "arista_eos",
    "juniper": "juniper_junos",
}


# ===== Scrapli 平台 → ntc-templates 平台映射 =====
NTC_PLATFORM_MAP: dict[str, str] = {
    "hp_comware": "hp_comware",
    "huawei_vrp": "huawei_vrp",
    "cisco_iosxe": "cisco_ios",
    "cisco_ios": "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "arista_eos": "arista_eos",
    "juniper_junos": "juniper_junos",
}


# ===== 统一命令接口 → 平台具体命令映射 =====
# 注意：cisco_ios 与 cisco_iosxe 命令相同，通过 _expand_cisco_commands 自动复制


def _expand_cisco_commands(cmd_map: dict[str, str]) -> dict[str, str]:
    """将 cisco_iosxe 命令自动复制到 cisco_ios（两者命令相同）。

    Args:
        cmd_map: 命令映射字典

    Returns:
        dict[str, str]: 更新后的命令映射字典
    """
    if "cisco_iosxe" in cmd_map and "cisco_ios" not in cmd_map:
        cmd_map["cisco_ios"] = cmd_map["cisco_iosxe"]
    return cmd_map


COMMAND_MAP: dict[str, dict[str, str]] = {
    # 配置备份
    "backup_config": _expand_cisco_commands(
        {
            "hp_comware": "display current-configuration",
            "huawei_vrp": "display current-configuration",
            "cisco_iosxe": "show running-config",
            "cisco_nxos": "show running-config",
            "arista_eos": "show running-config",
            "juniper_junos": "show configuration | display set",
        }
    ),
    # 版本信息
    "version": _expand_cisco_commands(
        {
            "hp_comware": "display version",
            "huawei_vrp": "display version",
            "cisco_iosxe": "show version",
            "cisco_nxos": "show version",
            "arista_eos": "show version",
            "juniper_junos": "show version",
        }
    ),
    # ARP 表
    "arp_table": _expand_cisco_commands(
        {
            "hp_comware": "display arp",
            "huawei_vrp": "display arp",
            "cisco_iosxe": "show ip arp",
            "cisco_nxos": "show ip arp",
            "arista_eos": "show ip arp",
            "juniper_junos": "show arp",
        }
    ),
    # MAC 地址表
    "mac_table": _expand_cisco_commands(
        {
            "hp_comware": "display mac-address",
            "huawei_vrp": "display mac-address",
            "cisco_iosxe": "show mac address-table",
            "cisco_nxos": "show mac address-table",
            "arista_eos": "show mac address-table",
            "juniper_junos": "show ethernet-switching table",
        }
    ),
    # LLDP 邻居
    "lldp_neighbors": _expand_cisco_commands(
        {
            "hp_comware": "display lldp neighbor-information list",
            "huawei_vrp": "display lldp neighbor brief",
            "cisco_iosxe": "show lldp neighbors",
            "cisco_nxos": "show lldp neighbors",
            "arista_eos": "show lldp neighbors",
            "juniper_junos": "show lldp neighbors",
        }
    ),
    # 接口状态
    "interface_brief": _expand_cisco_commands(
        {
            "hp_comware": "display interface brief",
            "huawei_vrp": "display interface brief",
            "cisco_iosxe": "show interfaces status",
            "cisco_nxos": "show interface status",
            "arista_eos": "show interfaces status",
            "juniper_junos": "show interfaces terse",
        }
    ),
    # VLAN 信息
    "vlan": _expand_cisco_commands(
        {
            "hp_comware": "display vlan brief",
            "huawei_vrp": "display vlan",
            "cisco_iosxe": "show vlan brief",
            "cisco_nxos": "show vlan",
            "arista_eos": "show vlan",
            "juniper_junos": "show vlans",
        }
    ),
}


# ===== Scrapli 连接默认参数 =====
SCRAPLI_DEFAULTS: dict[str, Any] = {
    "auth_strict_key": False,
    "ssh_config_file": "",
    "transport": "ssh2",
    "timeout_socket": 15,
    "timeout_transport": 30,
    "timeout_ops": 60,
}


# ===== 关闭分页命令 =====
_CISCO_PAGING_COMMANDS = [
    "terminal datadump",  # 某些 Cisco 设备需要此命令而非 terminal length 0
    "terminal length 0",
    "terminal pager 0",
    "no page",
    "terminal length 0\nterminal width 512",
]

PAGING_DISABLE_COMMANDS: dict[str, list[str]] = {
    "cisco_iosxe": _CISCO_PAGING_COMMANDS,
    "cisco_ios": _CISCO_PAGING_COMMANDS,  # 复用 iosxe 配置
    "cisco_nxos": [
        "terminal length 0",
        "terminal pager 0",
        "no page",
    ],
    "huawei_vrp": [
        "screen-length 0 temporary",
        "screen-length 0",
    ],
    "hp_comware": [
        "screen-length disable",
        "screen-length 0 temporary",
    ],
    "arista_eos": [
        "terminal length 0",
    ],
    "juniper_junos": [
        "set cli screen-length 0",
    ],
}


# ===== 平台特定 Scrapli 参数 =====
_CISCO_SCRAPLI_OPTIONS: dict[str, Any] = {
    "auth_strict_key": False,
    "ssh_config_file": "",
    "transport": "ssh2",
    "timeout_socket": 10,
    "timeout_transport": 60,
    "timeout_ops": 60,
}

PLATFORM_SCRAPLI_OPTIONS: dict[str, dict[str, Any]] = {
    "hp_comware": {
        "auth_strict_key": False,
        "ssh_config_file": "",
        "transport": "ssh2",
    },
    "huawei_vrp": {
        "auth_strict_key": False,
        "ssh_config_file": "",
        "transport": "ssh2",
    },
    "cisco_iosxe": _CISCO_SCRAPLI_OPTIONS,
    "cisco_ios": _CISCO_SCRAPLI_OPTIONS,  # 复用 iosxe 配置
}


# ===== 厂商/平台别名映射（模块级常量，避免每次调用重建）=====
_VENDOR_PLATFORM_ALIASES: dict[str, str] = {
    # Huawei
    "vrp": "huawei_vrp",
    "huawei_vrp": "huawei_vrp",
    "huawei": "huawei_vrp",
    # H3C / HP Comware
    "comware": "hp_comware",
    "hp_comware": "hp_comware",
    "h3c": "hp_comware",
    # Cisco
    "iosxe": "cisco_iosxe",
    "cisco_iosxe": "cisco_iosxe",
    "cisco_ios": "cisco_iosxe",
    "nxos": "cisco_nxos",
    "cisco_nxos": "cisco_nxos",
    "cisco": "cisco_iosxe",
    # Arista
    "arista": "arista_eos",
    "arista_eos": "arista_eos",
    # Juniper
    "juniper": "juniper_junos",
    "juniper_junos": "juniper_junos",
}


# 默认平台（当无法识别厂商时使用）
DEFAULT_PLATFORM = "hp_comware"


def get_platform_for_vendor(vendor: str) -> str:
    """
    根据厂商获取 Scrapli 平台标识。

    Args:
        vendor: 厂商名称 (h3c, huawei, cisco 等)

    Returns:
        str: Scrapli 平台标识 (hp_comware, huawei_vrp, cisco_iosxe 等)

    Raises:
        ValueError: 不支持的平台/厂商
    """
    v = (vendor or "").strip().lower().replace("-", "_").replace(" ", "_")

    # 使用模块级常量，避免每次调用重建字典
    if v in _VENDOR_PLATFORM_ALIASES:
        return _VENDOR_PLATFORM_ALIASES[v]
    if v in PLATFORM_SCRAPLI_OPTIONS:
        return v
    if v in VENDOR_PLATFORM_MAP:
        return VENDOR_PLATFORM_MAP[v]
    raise ValueError(f"不支持的平台/厂商: {vendor}")


def get_scrapli_platform(vendor: str | None, default: str | None = None) -> str:
    """
    根据厂商名称获取 Scrapli 平台标识（带默认值，不抛异常）。

    这是 get_platform_for_vendor 的安全版本，当厂商无法识别时返回默认值而不是抛出异常。

    Args:
        vendor: 厂商名称（不区分大小写）
        default: 自定义默认值，为 None 时使用 DEFAULT_PLATFORM

    Returns:
        Scrapli 平台标识
    """
    if not vendor:
        return default if default is not None else DEFAULT_PLATFORM

    try:
        return get_platform_for_vendor(vendor)
    except ValueError:
        return default if default is not None else DEFAULT_PLATFORM


def get_ntc_platform(scrapli_platform: str) -> str:
    """
    根据 Scrapli 平台获取 ntc-templates 平台标识。

    Args:
        scrapli_platform: Scrapli 平台标识

    Returns:
        str: ntc-templates 平台标识
    """
    return NTC_PLATFORM_MAP.get(scrapli_platform, scrapli_platform)


def get_command(command_type: str, platform: str) -> str:
    """
    获取指定平台的具体命令。

    Args:
        command_type: 命令类型 (backup_config, arp_table 等)
        platform: Scrapli 平台标识

    Returns:
        str: 平台具体命令

    Raises:
        ValueError: 未知的命令类型或平台
    """
    if command_type not in COMMAND_MAP:
        raise ValueError(f"未知的命令类型: {command_type}")

    platform_commands = COMMAND_MAP[command_type]
    if platform not in platform_commands:
        # 尝试使用 cisco_iosxe 作为默认
        if "cisco_iosxe" in platform_commands:
            return platform_commands["cisco_iosxe"]
        raise ValueError(f"平台 {platform} 不支持命令 {command_type}")

    return platform_commands[platform]


def get_scrapli_options(platform: str) -> dict[str, Any]:
    """
    获取指定平台的 Scrapli 连接参数。

    Args:
        platform: Scrapli 平台标识

    Returns:
        dict: Scrapli 连接参数
    """
    options = SCRAPLI_DEFAULTS.copy()
    if platform in PLATFORM_SCRAPLI_OPTIONS:
        options.update(PLATFORM_SCRAPLI_OPTIONS[platform])
    return options


def get_paging_disable_commands(platform: str) -> list[str]:
    """
    获取关闭分页的命令列表。

    Args:
        platform: Scrapli 平台标识

    Returns:
        list[str]: 关闭分页命令列表
    """
    p = (platform or "").strip().lower()
    if p in PAGING_DISABLE_COMMANDS:
        return PAGING_DISABLE_COMMANDS[p]
    if p.startswith("cisco_"):
        return PAGING_DISABLE_COMMANDS.get("cisco_iosxe", [])
    return []


def detect_vendor_from_banner(banner: str) -> str | None:
    """
    从 SSH Banner 识别设备厂商。

    Args:
        banner: SSH 连接 Banner 文本

    Returns:
        str | None: 识别出的厂商，未识别返回 None
    """
    banner_lower = banner.lower()

    vendor_patterns = {
        "h3c": ["h3c", "comware", "hp comware"],
        "huawei": ["huawei", "vrp", "versatile routing platform"],
        "cisco": ["cisco", "ios", "nx-os", "nexus"],
        "arista": ["arista", "eos"],
        "juniper": ["juniper", "junos"],
    }

    for vendor, patterns in vendor_patterns.items():
        for pattern in patterns:
            if pattern in banner_lower:
                return vendor

    return None


def detect_vendor_from_version(version_output: str) -> str | None:
    """
    从 version 命令输出识别设备厂商。

    Args:
        version_output: display version / show version 命令输出

    Returns:
        str | None: 识别出的厂商（h3c、huawei、cisco、arista、juniper），未识别返回 None
    """
    output_lower = version_output.lower()

    # 特征字符串 → 厂商映射
    signatures = {
        "h3c": ["h3c", "comware platform software", "new h3c technologies"],
        "huawei": ["huawei", "vrp (r) software", "versatile routing platform"],
        "cisco": [
            "cisco ios",
            "cisco nexus",
            "cisco adaptive security",
            "cisco internetwork operating system",
        ],
        "arista": ["arista", "eos"],
        "juniper": ["juniper", "junos"],
    }

    for vendor, keywords in signatures.items():
        for kw in keywords:
            if kw in output_lower:
                return vendor

    return None
