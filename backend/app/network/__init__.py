"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 12:50:00
@Docs: 网络自动化模块 (Network Automation Module).

包含 Nornir 框架配置、设备连接、命令执行和解析等功能。
"""

from app.network.nornir_config import init_nornir, init_nornir_from_db
from app.network.nornir_tasks import aggregate_results, backup_config, execute_command, get_arp_table, get_mac_table
from app.network.textfsm_parser import parse_command_output

__all__ = [
    "init_nornir",
    "init_nornir_from_db",
    "backup_config",
    "execute_command",
    "get_arp_table",
    "get_mac_table",
    "aggregate_results",
    "parse_command_output",
]
