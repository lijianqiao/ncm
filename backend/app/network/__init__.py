"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 12:50:00
@Docs: 网络自动化模块 (Network Automation Module).

包含 Nornir 框架配置、设备连接、命令执行和解析等功能。

注意：项目已全面迁移到异步模式，推荐使用 async_* 函数和 init_nornir_async。
"""

# 异步接口（推荐）
from app.network.async_runner import run_async_tasks
from app.network.async_tasks import (
    async_collect_config,
    async_deploy_from_host_data,
    async_get_lldp_neighbors,
    async_send_command,
)
from app.network.nornir_config import init_nornir_async, init_nornir_async_from_db

# 同步接口（仅用于向后兼容，不推荐使用）
from app.network.nornir_config import init_nornir, init_nornir_from_db
from app.network.nornir_tasks import aggregate_results, backup_config, execute_command, get_arp_table, get_mac_table
from app.network.textfsm_parser import parse_command_output

__all__ = [
    # 异步接口（推荐）
    "init_nornir_async",
    "init_nornir_async_from_db",
    "run_async_tasks",
    "async_send_command",
    "async_collect_config",
    "async_deploy_from_host_data",
    "async_get_lldp_neighbors",
    # 同步接口（向后兼容）
    "init_nornir",
    "init_nornir_from_db",
    "backup_config",
    "execute_command",
    "get_arp_table",
    "get_mac_table",
    "aggregate_results",
    "parse_command_output",
]
