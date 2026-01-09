"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: nornir_tasks.py
@DateTime: 2026-01-09 12:55:00
@Docs: Nornir 任务封装 (Nornir Task Wrappers).

封装常用的 Nornir 任务，如配置备份、命令执行等。
"""

from typing import Any

from nornir.core import Nornir
from nornir.core.task import AggregatedResult, MultiResult, Result, Task
from nornir_scrapli.tasks import send_command, send_commands, send_configs

from app.core.logger import logger
from app.network.textfsm_parser import parse_command_output


def backup_config(task: Task) -> Result:
    """
    备份设备配置的 Nornir 任务。

    根据设备平台自动选择正确的命令。

    Returns:
        Result: 包含配置内容的结果
    """
    platform = task.host.platform or ""

    # 根据平台选择备份命令
    command_mapping = {
        "cisco_iosxe": "show running-config",
        "cisco_ios": "show running-config",
        "cisco_nxos": "show running-config",
        "huawei_vrp": "display current-configuration",
        "hp_comware": "display current-configuration",
        "arista_eos": "show running-config",
        "juniper_junos": "show configuration | display set",
    }

    command = command_mapping.get(platform, "show running-config")

    result = task.run(task=send_command, command=command)

    return Result(
        host=task.host,
        result=result.result,
        changed=False,
    )


def execute_command(task: Task, command: str, parse: bool = False) -> Result:
    """
    在设备上执行单条命令。

    Args:
        task: Nornir 任务上下文
        command: 要执行的命令
        parse: 是否使用 TextFSM 解析输出

    Returns:
        Result: 包含命令输出的结果（原始文本或解析后的结构化数据）
    """
    result = task.run(task=send_command, command=command)
    raw_output = result.result

    if parse and task.host.platform:
        parsed = parse_command_output(
            platform=task.host.platform,
            command=command,
            output=raw_output,
        )
        return Result(
            host=task.host,
            result={"raw": raw_output, "parsed": parsed},
            changed=False,
        )

    return Result(
        host=task.host,
        result=raw_output,
        changed=False,
    )


def execute_commands(task: Task, commands: list[str]) -> Result:
    """
    在设备上执行多条命令。

    Args:
        task: Nornir 任务上下文
        commands: 命令列表

    Returns:
        Result: 包含所有命令输出的结果
    """
    result = task.run(task=send_commands, commands=commands)

    return Result(
        host=task.host,
        result=result.result,
        changed=False,
    )


def deploy_from_host_data(task: Task) -> Result:
    """根据 host.data['deploy_configs'] 下发配置（用于每台设备不同配置内容）。"""
    configs: list[str] = task.host.data.get("deploy_configs", [])  # type: ignore[assignment]
    if not configs:
        return Result(host=task.host, result={"status": "skipped", "message": "no deploy configs"}, changed=False)

    result = task.run(task=send_configs, configs=configs)
    return Result(host=task.host, result=result.result, changed=True)


def get_arp_table(task: Task) -> MultiResult:
    """获取设备 ARP 表（自动解析）。"""
    platform = task.host.platform or "cisco_ios"

    command_mapping = {
        "cisco_iosxe": "show ip arp",
        "cisco_ios": "show ip arp",
        "huawei_vrp": "display arp",
        "hp_comware": "display arp",
    }
    command = command_mapping.get(platform, "show ip arp")

    return task.run(task=execute_command, command=command, parse=True)


def get_mac_table(task: Task) -> MultiResult:
    """获取设备 MAC 地址表（自动解析）。"""
    platform = task.host.platform or "cisco_ios"

    command_mapping = {
        "cisco_iosxe": "show mac address-table",
        "cisco_ios": "show mac address-table",
        "huawei_vrp": "display mac-address",
        "hp_comware": "display mac-address",
    }
    command = command_mapping.get(platform, "show mac address-table")

    return task.run(task=execute_command, command=command, parse=True)


def get_lldp_neighbors(task: Task) -> MultiResult:
    """获取设备 LLDP 邻居信息（自动解析）。"""
    platform = task.host.platform or "cisco_ios"

    command_mapping = {
        "cisco_iosxe": "show lldp neighbors detail",
        "cisco_ios": "show lldp neighbors detail",
        "huawei_vrp": "display lldp neighbor brief",
        "hp_comware": "display lldp neighbor-information list",
    }
    command = command_mapping.get(platform, "show lldp neighbors detail")

    return task.run(task=execute_command, command=command, parse=True)


def aggregate_results(results: AggregatedResult) -> dict[str, Any]:
    """
    聚合 Nornir 任务结果。

    Args:
        results: Nornir AggregatedResult 对象

    Returns:
        dict: 包含成功/失败统计和详细结果的字典
    """
    success_hosts = []
    failed_hosts = []
    host_results = {}

    for host, multi_result in results.items():
        if multi_result.failed:
            failed_hosts.append(host)
            host_results[host] = {
                "status": "failed",
                "error": str(multi_result.exception) if multi_result.exception else "Unknown error",
            }
        else:
            success_hosts.append(host)
            # 获取最后一个结果（通常是主任务的结果）
            if multi_result:
                last_result = multi_result[-1]
                host_results[host] = {
                    "status": "success",
                    "result": last_result.result,
                }

    summary = {
        "total": len(results),
        "success": len(success_hosts),
        "failed": len(failed_hosts),
        "success_hosts": success_hosts,
        "failed_hosts": failed_hosts,
        "results": host_results,
    }

    logger.info(
        "Nornir 任务执行完成",
        total=summary["total"],
        success=summary["success"],
        failed=summary["failed"],
    )

    return summary


def run_backup_all(nr: Nornir) -> dict[str, Any]:
    """
    对所有设备执行配置备份。

    Args:
        nr: Nornir 实例

    Returns:
        dict: 聚合后的备份结果
    """
    logger.info("开始批量配置备份", hosts_count=len(nr.inventory.hosts))

    results = nr.run(task=backup_config)

    return aggregate_results(results)
