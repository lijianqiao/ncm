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
    """设备厂商类型。"""

    H3C = "h3c"
    HUAWEI = "huawei"
    CISCO = "cisco"
    ARISTA = "arista"
    JUNIPER = "juniper"


class ScrapliPlatform(str, Enum):
    """Scrapli 平台标识。"""

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
COMMAND_MAP: dict[str, dict[str, str]] = {
    # 配置备份
    "backup_config": {
        "hp_comware": "display current-configuration",
        "huawei_vrp": "display current-configuration",
        "cisco_iosxe": "show running-config",
        "cisco_ios": "show running-config",
        "cisco_nxos": "show running-config",
        "arista_eos": "show running-config",
        "juniper_junos": "show configuration | display set",
    },
    # 版本信息
    "version": {
        "hp_comware": "display version",
        "huawei_vrp": "display version",
        "cisco_iosxe": "show version",
        "cisco_ios": "show version",
        "cisco_nxos": "show version",
        "arista_eos": "show version",
        "juniper_junos": "show version",
    },
    # ARP 表
    "arp_table": {
        "hp_comware": "display arp",
        "huawei_vrp": "display arp",
        "cisco_iosxe": "show ip arp",
        "cisco_ios": "show ip arp",
        "cisco_nxos": "show ip arp",
        "arista_eos": "show ip arp",
        "juniper_junos": "show arp",
    },
    # MAC 地址表
    "mac_table": {
        "hp_comware": "display mac-address",
        "huawei_vrp": "display mac-address",
        "cisco_iosxe": "show mac address-table",
        "cisco_ios": "show mac address-table",
        "cisco_nxos": "show mac address-table",
        "arista_eos": "show mac address-table",
        "juniper_junos": "show ethernet-switching table",
    },
    # LLDP 邻居
    "lldp_neighbors": {
        "hp_comware": "display lldp neighbor-information list",
        "huawei_vrp": "display lldp neighbor brief",
        "cisco_iosxe": "show lldp neighbors detail",
        "cisco_ios": "show lldp neighbors detail",
        "cisco_nxos": "show lldp neighbors detail",
        "arista_eos": "show lldp neighbors",
        "juniper_junos": "show lldp neighbors",
    },
    # 接口状态
    "interface_brief": {
        "hp_comware": "display interface brief",
        "huawei_vrp": "display interface brief",
        "cisco_iosxe": "show interfaces status",
        "cisco_ios": "show interfaces status",
        "cisco_nxos": "show interface status",
        "arista_eos": "show interfaces status",
        "juniper_junos": "show interfaces terse",
    },
    # VLAN 信息
    "vlan": {
        "hp_comware": "display vlan brief",
        "huawei_vrp": "display vlan",
        "cisco_iosxe": "show vlan brief",
        "cisco_ios": "show vlan brief",
        "cisco_nxos": "show vlan",
        "arista_eos": "show vlan",
        "juniper_junos": "show vlans",
    },
}


# ===== Scrapli 连接默认参数 =====
SCRAPLI_DEFAULTS: dict[str, Any] = {
    "auth_strict_key": False,
    "ssh_config_file": False,
    "transport": "asyncssh",
    "timeout_socket": 15,
    "timeout_transport": 30,
    "timeout_ops": 60,
}


# ===== 平台特定 Scrapli 参数 =====
PLATFORM_SCRAPLI_OPTIONS: dict[str, dict[str, Any]] = {
    "hp_comware": {
        "auth_strict_key": False,
        "ssh_config_file": False,
        "transport": "asyncssh",
        "transport_options": {
            "encoding": "gb18030",
            "errors": "replace",
        },
    },
    "huawei_vrp": {
        "auth_strict_key": False,
        "ssh_config_file": False,
        "transport": "asyncssh",
        "transport_options": {
            "encoding": "gb18030",
            "errors": "replace",
        },
    },
    "cisco_iosxe": {
        "auth_strict_key": False,
        "ssh_config_file": False,
        "transport": "asyncssh",
    },
}


def get_platform_for_vendor(vendor: str) -> str:
    """
    根据厂商获取 Scrapli 平台标识。

    Args:
        vendor: 厂商名称 (h3c, huawei, cisco 等)

    Returns:
        str: Scrapli 平台标识 (hp_comware, huawei_vrp, cisco_iosxe 等)
    """
    return VENDOR_PLATFORM_MAP.get(vendor.lower(), "cisco_iosxe")


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
        str | None: 识别出的厂商，未识别返回 None
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
