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

from app.core.config import settings
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.network.otp_utils import handle_otp_auth_failure_sync, resolve_otp_password_sync
from app.network.platform_config import get_command
from app.network.scrapli_utils import disable_paging, is_command_error, send_command_with_paging
from app.network.textfsm_parser import parse_command_output


def _apply_dynamic_auth(task: Task) -> None:
    """应用动态认证到 Nornir Host（使用统一的 OTP 解析逻辑）。

    Args:
        task: Nornir 任务上下文
    """
    auth_type = task.host.data.get("auth_type")
    host_data = {"name": task.host.name, **dict(task.host.data)}

    otp_password = resolve_otp_password_sync(auth_type, host_data)
    if otp_password is not None:
        task.host.password = otp_password


def backup_config(task: Task) -> Result:
    """
    备份设备配置的 Nornir 任务。

    根据设备平台自动选择正确的命令。

    Args:
        task: Nornir 任务上下文

    Returns:
        Result: 包含配置内容的结果

    Raises:
        ScrapliAuthenticationFailed: 认证失败时抛出（会先调用 handle_otp_auth_failure_sync）
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

    Raises:
        ScrapliAuthenticationFailed: 认证失败时抛出（会先调用 handle_otp_auth_failure_sync）
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

    Raises:
        ScrapliAuthenticationFailed: 认证失败时抛出（会先调用 handle_otp_auth_failure_sync）
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
    """根据 host.data['deploy_configs'] 下发配置（用于每台设备不同配置内容）。

    Args:
        task: Nornir 任务上下文，host.data 中需包含 'deploy_configs' 键

    Returns:
        Result: 包含下发结果的任务结果

    Raises:
        OTPRequiredException: OTP 认证失败时抛出
        NornirSubTaskError: 子任务失败时抛出
        Exception: 其他下发异常
    """
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
                # 检查子任务异常是否是 OTPRequiredException
                if isinstance(sub_exc, OTPRequiredException):
                    raise sub_exc from None
        error_text = "\n".join([x for x in detail_parts if x])
        logger.error("下发子任务失败", host=str(task.host), error=error_text, exc_info=True)
        return Result(
            host=task.host,
            result={"error": error_text},
            changed=False,
            failed=True,
        )
    except OTPRequiredException:
        # OTP 异常必须传播，让 Celery 任务处理
        raise
    except Exception as e:
        logger.error("下发任务失败", host=str(task.host), error=str(e), exc_info=True)
        return Result(
            host=task.host,
            result={"error": str(e)},
            changed=False,
            failed=True,
        )


def get_arp_table(task: Task) -> MultiResult:
    """获取设备 ARP 表（自动解析）。

    Args:
        task: Nornir 任务上下文对象

    Returns:
        MultiResult: 包含解析后 ARP 表数据的多结果对象
    """
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("arp_table", platform)
    except ValueError:
        command = "show ip arp"

    return task.run(task=execute_command, command=command, parse=True)


def get_mac_table(task: Task) -> MultiResult:
    """获取设备 MAC 地址表（自动解析）。

    Args:
        task: Nornir Task 对象

    Returns:
        MultiResult: 包含解析后的 MAC 表数据，result 为 {"raw": str, "parsed": list[dict]}
    """
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("mac_table", platform)
    except ValueError:
        command = "show mac address-table"

    return task.run(task=execute_command, command=command, parse=True)


def get_lldp_neighbors(task: Task) -> MultiResult:
    """获取设备 LLDP 邻居信息（自动解析）。

    Args:
        task: Nornir Task 对象

    Returns:
        MultiResult: 包含解析后的 LLDP 邻居数据，result 为 {"raw": str, "parsed": list[dict]}
    """
    platform = task.host.platform or "cisco_iosxe"

    # 使用统一的命令映射
    try:
        command = get_command("lldp_neighbors", platform)
    except ValueError:
        command = "show lldp neighbors detail"

    return task.run(task=execute_command, command=command, parse=True)


def _is_otp_error_text(error_text: str) -> bool:
    """检查错误文本是否为 OTP 相关错误。

    Args:
        error_text: 错误文本

    Returns:
        bool: 如果错误文本包含 OTP 相关关键词则返回 True
    """
    text = (error_text or "").lower()
    return "otp" in text and ("过期" in text or "required" in text or "认证" in text)


def _handle_otp_exception(
    otp_exc: OTPRequiredException,
    error_text: str,
    otp_failed_device_ids: list[str],
    otp_required_info: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    处理 OTPRequiredException，返回 (host_result, updated_otp_info)。

    Args:
        otp_exc: OTPRequiredException 异常对象
        error_text: 错误文本
        otp_failed_device_ids: 失败设备 ID 列表（会被更新）
        otp_required_info: 现有的 OTP 需求信息（可选）

    Returns:
        tuple[dict[str, Any], dict[str, Any] | None]: (主机结果字典, 更新后的 OTP 需求信息)
    """
    host_result = {
        "status": "otp_required",
        "error": error_text,
        "result": None,
        "otp_dept_id": str(otp_exc.dept_id),
        "otp_device_group": otp_exc.device_group,
    }
    if otp_exc.failed_devices:
        otp_failed_device_ids.extend(str(did) for did in otp_exc.failed_devices)

    if otp_required_info is None:
        otp_required_info = {
            "otp_required": True,
            "otp_dept_id": str(otp_exc.dept_id),
            "otp_device_group": otp_exc.device_group,
        }
    return host_result, otp_required_info


def _extract_error_and_exception(multi_result: MultiResult) -> tuple[str, BaseException | None]:
    """从 MultiResult 中提取错误信息和异常。

    Args:
        multi_result: Nornir MultiResult 对象

    Returns:
        tuple[str, BaseException | None]: (错误信息字符串, 异常对象或 None)
    """
    if multi_result.exception:
        return str(multi_result.exception), multi_result.exception

    if multi_result:
        last_result = multi_result[-1]
        if isinstance(last_result.result, dict) and last_result.result.get("error"):
            return str(last_result.result.get("error")), None
        if last_result.exception:
            return str(last_result.exception), last_result.exception

    return "Unknown error", None


def aggregate_results(results: AggregatedResult) -> dict[str, Any]:
    """
    聚合 Nornir 任务结果。

    Args:
        results: Nornir AggregatedResult 对象

    Returns:
        dict[str, Any]: 包含成功/失败统计和详细结果的字典：
        - total (int): 总设备数
        - success (int): 成功设备数
        - failed (int): 失败设备数
        - success_hosts (list[str]): 成功主机名列表
        - failed_hosts (list[str]): 失败主机名列表
        - results (dict): 各主机的详细结果
        - otp_failed_device_ids (list[str]): OTP 失败设备 ID 列表
        - otp_required (bool): 是否需要 OTP（可选）
        - otp_dept_id (str): OTP 部门 ID（可选）
        - otp_device_group (str): OTP 设备组（可选）
    """
    success_hosts: list[str] = []
    failed_hosts: list[str] = []
    host_results: dict[str, dict[str, Any]] = {}
    otp_required_info: dict[str, Any] | None = None
    otp_failed_device_ids: list[str] = []

    for host, multi_result in results.items():
        if multi_result.failed:
            failed_hosts.append(host)
            error_text, exception = _extract_error_and_exception(multi_result)

            # 处理 OTPRequiredException
            if isinstance(exception, OTPRequiredException):
                host_results[host], otp_required_info = _handle_otp_exception(
                    exception, error_text, otp_failed_device_ids, otp_required_info
                )
                continue

            # 处理文本中的 OTP 错误
            if _is_otp_error_text(error_text):
                host_results[host] = {"status": "otp_required", "error": error_text, "result": None}
                if otp_required_info is None:
                    otp_required_info = {"otp_required": True}
                continue

            # 普通失败
            host_results[host] = {"status": "failed", "error": error_text}
        else:
            success_hosts.append(host)
            if multi_result:
                host_results[host] = {"status": "success", "result": multi_result[-1].result}

    summary: dict[str, Any] = {
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
        dict[str, Any]: 聚合后的备份结果（格式同 aggregate_results）

    Raises:
        ScrapliAuthenticationFailed: 认证失败时抛出
    """
    logger.info("开始批量配置备份", hosts_count=len(nr.inventory.hosts))

    results = nr.run(task=backup_config)

    return aggregate_results(results)
