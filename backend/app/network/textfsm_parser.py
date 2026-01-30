"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: textfsm_parser.py
@DateTime: 2026-01-09 12:50:00
@Docs: TextFSM 解析器工具 (TextFSM Parser Utility).

使用 ntc-templates 和自定义模板将网络设备的非结构化命令输出转换为结构化数据。
优先使用自定义模板，fallback 到 ntc-templates。
"""

from pathlib import Path
from typing import Any

import textfsm
from ntc_templates.parse import parse_output

from app.core.logger import logger
from app.network.platform_config import get_command, get_ntc_platform
from app.network.templates import get_template_path


def _parse_with_custom_template(
    template_path: str,
    output: str,
) -> list[dict[str, Any]]:
    """
    使用自定义模板解析输出。

    Args:
        template_path: TextFSM 模板文件路径
        output: 命令输出文本

    Returns:
        list[dict]: 解析后的结构化数据
    """
    with open(template_path, encoding="utf-8") as template_file:
        fsm = textfsm.TextFSM(template_file)
        result = fsm.ParseText(output)

        # 将结果转换为字典列表
        parsed = []
        for row in result:
            record = {}
            for i, header in enumerate(fsm.header):
                record[header.lower()] = row[i]
            parsed.append(record)

        return parsed


def parse_command_output(
    platform: str,
    command: str,
    output: str,
) -> list[dict[str, Any]]:
    """
    解析命令输出，优先使用自定义模板，fallback 到 ntc-templates。

    Args:
        platform: 设备平台 (cisco_ios, huawei_vrp, hp_comware 等)
        command: 执行的命令 (如 show ip arp, display arp)
        output: 命令的原始文本输出

    Returns:
        list[dict]: 解析后的结构化数据列表
    """
    # 获取 ntc-templates 平台名（复用 platform_config 的映射）
    ntc_platform = get_ntc_platform(platform)

    # 1. 优先尝试自定义模板
    custom_template = get_template_path(ntc_platform, command)
    if custom_template:
        try:
            parsed = _parse_with_custom_template(custom_template, output)
            logger.debug(
                "使用自定义模板解析成功",
                platform=ntc_platform,
                command=command,
                template=Path(custom_template).name,
                records_count=len(parsed),
            )
            return parsed
        except Exception as e:
            logger.warning(
                "自定义模板解析失败，尝试 ntc-templates",
                platform=ntc_platform,
                command=command,
                error=str(e),
            )

    # 2. Fallback 到 ntc-templates
    try:
        parsed = parse_output(platform=ntc_platform, command=command, data=output)
        logger.debug(
            "ntc-templates 解析成功",
            platform=ntc_platform,
            command=command,
            records_count=len(parsed) if parsed else 0,
        )
        return parsed if parsed else []
    except Exception as e:
        logger.warning(
            "TextFSM 解析失败",
            platform=ntc_platform,
            command=command,
            error=str(e),
        )
        # 返回空列表而非抛出异常，让调用方决定如何处理
        return []


# ===== 常用命令的解析快捷方法 =====


def _get_command_safe(command_type: str, platform: str, fallback: str) -> str:
    """安全获取命令，失败时返回 fallback。

    Args:
        command_type: 命令类型（如 "arp_table"）
        platform: 设备平台
        fallback: 备用命令

    Returns:
        str: 平台对应的命令，如果获取失败则返回 fallback
    """
    try:
        return get_command(command_type, platform)
    except ValueError:
        return fallback


def parse_arp_table(platform: str, output: str) -> list[dict[str, Any]]:
    """
    解析 ARP 表输出。

    Args:
        platform: 设备平台
        output: ARP 表命令输出

    Returns:
        list[dict[str, Any]]: 包含 ip_address, mac_address, interface 等字段的字典列表
    """
    command = _get_command_safe("arp_table", platform, "show ip arp")
    return parse_command_output(platform, command, output)


def parse_mac_table(platform: str, output: str) -> list[dict[str, Any]]:
    """
    解析 MAC 地址表输出。

    Args:
        platform: Scrapli 平台标识
        output: MAC 地址表命令的原始输出

    Returns:
        list[dict[str, Any]]: 解析后的 MAC 地址表数据，每项包含 vlan、mac_address、type、port 等字段
    """
    command = _get_command_safe("mac_table", platform, "show mac address-table")
    return parse_command_output(platform, command, output)


def parse_lldp_neighbors(platform: str, output: str) -> list[dict[str, Any]]:
    """
    解析 LLDP 邻居信息。

    Args:
        platform: Scrapli 平台标识
        output: LLDP 邻居命令的原始输出

    Returns:
        list[dict[str, Any]]: 解析后的 LLDP 邻居数据，每项包含 local_interface、neighbor、neighbor_interface 等字段
    """
    command = _get_command_safe("lldp_neighbors", platform, "show lldp neighbors detail")
    return parse_command_output(platform, command, output)


def parse_interface_status(platform: str, output: str) -> list[dict[str, Any]]:
    """
    解析接口状态。

    Args:
        platform: Scrapli 平台标识
        output: 接口状态命令的原始输出

    Returns:
        list[dict[str, Any]]: 解析后的接口状态数据，每项包含 port、status、vlan、duplex、speed 等字段
    """
    command = _get_command_safe("interface_brief", platform, "show interfaces status")
    return parse_command_output(platform, command, output)


def parse_version(platform: str, output: str) -> list[dict[str, Any]]:
    """
    解析版本信息。

    Args:
        platform: 设备平台标识
        output: 版本命令的原始输出

    Returns:
        list[dict[str, Any]]: 解析后的版本数据，每个元素包含 version、model、uptime 等字段
    """
    command = _get_command_safe("version", platform, "show version")
    return parse_command_output(platform, command, output)
