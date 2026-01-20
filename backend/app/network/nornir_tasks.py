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
from nornir.core.exceptions import NornirSubTaskError
from nornir.core.task import AggregatedResult, MultiResult, Result, Task
from nornir_scrapli.tasks import send_command, send_commands, send_configs
from scrapli.exceptions import ScrapliAuthenticationFailed

from app.celery.base import run_async
from app.core.config import settings
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.network.otp_utils import (
    get_manual_otp_or_raise,
    get_seed_otp,
    handle_otp_auth_failure_sync,
)
from app.network.platform_config import get_command
from app.network.scrapli_utils import disable_paging, is_command_error, send_command_with_paging
from app.network.textfsm_parser import parse_command_output


def _apply_dynamic_auth(task: Task) -> None:
    auth_type = task.host.data.get("auth_type")
    if auth_type == "otp_seed":
        encrypted_seed = task.host.data.get("otp_seed_encrypted")
        if not encrypted_seed:
            raise ValueError("缺少 OTP 种子，无法生成验证码")
        task.host.password = run_async(get_seed_otp(str(encrypted_seed)))
        return

    if auth_type != "otp_manual":
        return

    dept_id_raw = task.host.data.get("dept_id")
    device_group = task.host.data.get("device_group")
    if not dept_id_raw or not device_group:
        raise ValueError("缺少 OTP 所需的部门/分层信息，无法获取验证码")

    from uuid import UUID

    dept_id = UUID(str(dept_id_raw))
    failed_id = task.host.data.get("device_id") or task.host.name
    otp_code = run_async(get_manual_otp_or_raise(dept_id, str(device_group), str(failed_id)))
    task.host.password = otp_code


def backup_config(task: Task) -> Result:
    """
    备份设备配置的 Nornir 任务。

    根据设备平台自动选择正确的命令。

    Returns:
        Result: 包含配置内容的结果
    """
    platform = task.host.platform or "cisco_iosxe"
    _apply_dynamic_auth(task)

    # 使用统一的命令映射
    try:
        command = get_command("backup_config", platform)
    except ValueError:
        command = "show running-config"

    timeout_ops = max(int(settings.ASYNC_SSH_TIMEOUT or 0), 30)

    try:
        scrapli_conn = task.host.get_connection("scrapli", task.nornir.config)
    except ScrapliAuthenticationFailed as e:
        # OTP 认证失败时立即抛出 428，让前端重新输入
        handle_otp_auth_failure_sync(dict(task.host.data), e)
        raise  # 永远不会到达，但满足类型检查

    disable_paging(scrapli_conn, platform)
    prompt = None
    try:
        prompt = scrapli_conn.get_prompt()
    except Exception as e:
        logger.debug("获取提示符失败", host=str(task.host), error=str(e))
        if platform.startswith("cisco_"):
            prompt = "#"

    output = send_command_with_paging(scrapli_conn, command, timeout_ops=timeout_ops, prompt=prompt)

    return Result(
        host=task.host,
        result=output,
        changed=False,
        failed=is_command_error(output),
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
    _apply_dynamic_auth(task)

    # 显式触发连接以捕获认证错误
    try:
        task.host.get_connection("scrapli", task.nornir.config)
    except ScrapliAuthenticationFailed as e:
        handle_otp_auth_failure_sync(dict(task.host.data), e)
        raise

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
        Result: 包含命令输出的结果
    """
    _apply_dynamic_auth(task)

    # 显式触发连接以捕获认证错误
    try:
        task.host.get_connection("scrapli", task.nornir.config)
    except ScrapliAuthenticationFailed as e:
        handle_otp_auth_failure_sync(dict(task.host.data), e)
        raise

    result = task.run(task=send_commands, commands=commands)

    return Result(
        host=task.host,
        result=result.result,
        changed=False,
    )


def deploy_from_host_data(task: Task) -> Result:
    """根据 host.data['deploy_configs'] 下发配置（用于每台设备不同配置内容）。"""
    _apply_dynamic_auth(task)
    configs: list[str] = task.host.data.get("deploy_configs", [])  # type: ignore[assignment]
    if not configs:
        return Result(host=task.host, result={"status": "skipped", "message": "no deploy configs"}, changed=False)

    try:
        # 显式触发连接以捕获认证错误
        try:
            task.host.get_connection("scrapli", task.nornir.config)
        except ScrapliAuthenticationFailed as e:
            handle_otp_auth_failure_sync(dict(task.host.data), e)
            raise

        result = task.run(task=send_configs, configs=configs)
        return Result(host=task.host, result=result.result, changed=True)
    except NornirSubTaskError as e:
        # nornir_scrapli 的子任务异常默认只会给出 "Subtask ... failed"，这里尽量提取底层异常信息
        detail_parts: list[str] = [str(e)]
        sub = getattr(e, "result", None)
        if sub is not None:
            sub_name = getattr(sub, "name", None)
            sub_exc = getattr(sub, "exception", None)
            if sub_name:
                detail_parts.append(f"子任务: {sub_name}")
            if sub_exc:
                detail_parts.append(f"异常: {sub_exc}")
        error_text = "\n".join([x for x in detail_parts if x])
        logger.error("下发子任务失败", host=str(task.host), error=error_text, exc_info=True)
        return Result(
            host=task.host,
            result={"error": error_text},
            changed=False,
            failed=True,
        )
    except Exception as e:
        logger.error("下发任务失败", host=str(task.host), error=str(e), exc_info=True)
        return Result(
            host=task.host,
            result={"error": str(e)},
            changed=False,
            failed=True,
        )


def get_arp_table(task: Task) -> MultiResult:
    """获取设备 ARP 表（自动解析）。"""
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("arp_table", platform)
    except ValueError:
        command = "show ip arp"

    return task.run(task=execute_command, command=command, parse=True)


def get_mac_table(task: Task) -> MultiResult:
    """获取设备 MAC 地址表（自动解析）。"""
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("mac_table", platform)
    except ValueError:
        command = "show mac address-table"

    return task.run(task=execute_command, command=command, parse=True)


def get_lldp_neighbors(task: Task) -> MultiResult:
    """获取设备 LLDP 邻居信息（自动解析）。"""
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("lldp_neighbors", platform)
    except ValueError:
        command = "show lldp neighbors detail"

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
    otp_required_info: dict[str, Any] | None = None
    otp_failed_device_ids: list[str] = []

    def _is_otp_error(error_text: str) -> bool:
        text = (error_text or "").lower()
        return "otp" in text and ("过期" in text or "required" in text or "认证" in text)

    for host, multi_result in results.items():
        if multi_result.failed:
            failed_hosts.append(host)

            error_text = "Unknown error"
            if multi_result.exception:
                error_text = str(multi_result.exception)
                if isinstance(multi_result.exception, OTPRequiredException):
                    otp_required = multi_result.exception
                    host_results[host] = {
                        "status": "otp_required",
                        "error": error_text,
                        "result": None,
                        "otp_dept_id": str(otp_required.dept_id),
                        "otp_device_group": otp_required.device_group,
                    }
                    if otp_required.failed_devices:
                        for did in otp_required.failed_devices:
                            otp_failed_device_ids.append(str(did))
                    if otp_required_info is None:
                        otp_required_info = {
                            "otp_required": True,
                            "otp_dept_id": str(otp_required.dept_id),
                            "otp_device_group": otp_required.device_group,
                        }
                    continue
                if _is_otp_error(error_text):
                    host_results[host] = {
                        "status": "otp_required",
                        "error": error_text,
                        "result": None,
                    }
                    if otp_required_info is None:
                        otp_required_info = {"otp_required": True}
                    continue
            elif multi_result:
                # 若任务函数内部捕获并返回了 failed Result，则从最后一个结果里取 error
                last_result = multi_result[-1]
                if isinstance(last_result.result, dict) and last_result.result.get("error"):
                    error_text = str(last_result.result.get("error"))
                elif last_result.exception:
                    error_text = str(last_result.exception)
                    if isinstance(last_result.exception, OTPRequiredException):
                        otp_required = last_result.exception
                        host_results[host] = {
                            "status": "otp_required",
                            "error": error_text,
                            "result": None,
                            "otp_dept_id": str(otp_required.dept_id),
                            "otp_device_group": otp_required.device_group,
                        }
                        if otp_required.failed_devices:
                            for did in otp_required.failed_devices:
                                otp_failed_device_ids.append(str(did))
                        if otp_required_info is None:
                            otp_required_info = {
                                "otp_required": True,
                                "otp_dept_id": str(otp_required.dept_id),
                                "otp_device_group": otp_required.device_group,
                            }
                        continue
                    if _is_otp_error(error_text):
                        host_results[host] = {
                            "status": "otp_required",
                            "error": error_text,
                            "result": None,
                        }
                        if otp_required_info is None:
                            otp_required_info = {"otp_required": True}
                        continue

            host_results[host] = {
                "status": "failed",
                "error": error_text,
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
        "otp_failed_device_ids": otp_failed_device_ids,
    }
    if otp_required_info:
        summary.update(otp_required_info)

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
