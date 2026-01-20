"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: async_tasks.py
@DateTime: 2026-01-14 00:30:00
@Docs: Scrapli 异步任务函数库。

提供通用的异步网络设备操作任务，配合 AsyncRunner 使用。
所有函数都是独立的异步函数，接收 Host 对象并返回执行结果。
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from scrapli import Scrapli
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout
from scrapli.response import MultiResponse, Response

from app.core.config import settings
from app.core.logger import logger
from app.network.otp_utils import get_manual_otp_or_raise, get_seed_otp, handle_otp_auth_failure
from app.network.platform_config import get_scrapli_options
from app.network.scrapli_utils import disable_paging, send_command_with_paging

if TYPE_CHECKING:
    from nornir.core.inventory import Host


def _get_scrapli_kwargs(host: "Host") -> dict[str, Any]:
    """
    从 Nornir Host 对象提取 Scrapli 连接参数。

    使用 platform_config.py 中的统一配置作为基础，
    然后覆盖主机特定的连接信息和超时参数。

    Args:
        host: Nornir Host 对象

    Returns:
        Scrapli 连接参数字典
    """
    from app.network.platform_config import get_platform_for_vendor

    raw_platform = host.platform or "hp_comware"

    platform = get_platform_for_vendor(raw_platform)

    # 从 platform_config.py 获取平台特定的 Scrapli 配置
    base_options = get_scrapli_options(platform)

    # 从 host 的 connection_options 中获取额外配置（优先级更高）
    extras = {}
    if host.connection_options and "scrapli" in host.connection_options:
        extras = host.connection_options["scrapli"].extras or {}

    # 合并配置：base_options → extras → 固定覆盖项
    base_timeout_socket = base_options.get("timeout_socket")
    base_timeout_transport = base_options.get("timeout_transport")
    base_timeout_ops = base_options.get("timeout_ops")

    def _as_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    timeout_socket = max(_as_int(base_timeout_socket), int(settings.ASYNC_SSH_CONNECT_TIMEOUT))
    timeout_transport = max(_as_int(base_timeout_transport), int(settings.ASYNC_SSH_CONNECT_TIMEOUT))
    timeout_ops = max(_as_int(base_timeout_ops), int(settings.ASYNC_SSH_TIMEOUT))

    result = {
        **base_options,
        **extras,
        # 主机特定信息（必须覆盖）
        "host": host.hostname,
        "auth_username": host.username,
        "auth_password": host.password,
        "port": host.port or 22,
        "platform": platform,
        # 使用配置文件中的超时参数
        "timeout_socket": timeout_socket,
        "timeout_transport": timeout_transport,
        "timeout_ops": timeout_ops,
    }
    if platform.startswith("cisco_") and not result.get("auth_secondary"):
        result["auth_secondary"] = result.get("auth_password") or ""

    return result


async def _apply_otp_manual_password(host: "Host", kwargs: dict[str, Any]) -> dict[str, Any]:
    auth_type = host.data.get("auth_type")
    if auth_type == "otp_seed":
        encrypted_seed = host.data.get("otp_seed_encrypted")
        kwargs["auth_password"] = await get_seed_otp(str(encrypted_seed))
        return kwargs

    if auth_type != "otp_manual":
        return kwargs

    dept_id_raw = host.data.get("dept_id")
    device_group = host.data.get("device_group")
    if not dept_id_raw or not device_group:
        raise ValueError("缺少 OTP 所需的部门/分层信息，无法获取验证码")

    from uuid import UUID

    dept_id = UUID(str(dept_id_raw))
    failed_id = host.data.get("device_id") or host.name
    kwargs["auth_password"] = await get_manual_otp_or_raise(dept_id, str(device_group), str(failed_id))
    return kwargs


async def _run_send_command(
    host: "Host",
    kwargs: dict[str, Any],
    command: str,
    *,
    timeout_ops: float | None = None,
) -> Response:
    start = time.monotonic()
    stage = "init"
    safe_command = (command or "").strip().splitlines()[0][:120]

    def _sync() -> Response:
        nonlocal stage
        conn = Scrapli(**kwargs)
        try:
            stage = "open"
            logger.info("Scrapli 打开连接", host=host.name, device=host.hostname, platform=kwargs.get("platform"))
            conn.open()
            logger.info(
                "Scrapli 连接已打开",
                host=host.name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            stage = "send_command"
            logger.info(
                "Scrapli 发送命令",
                host=host.name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                command=safe_command,
                timeout_ops=timeout_ops,
            )
            response = conn.send_command(command, timeout_ops=timeout_ops)
            logger.info(
                "Scrapli 命令返回",
                host=host.name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                command=safe_command,
                failed=response.failed,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                result_len=len(response.result or ""),
            )
            return response
        finally:
            try:
                stage = "close"
                conn.close()
                logger.info(
                    "Scrapli 连接已关闭",
                    host=host.name,
                    device=host.hostname,
                    platform=kwargs.get("platform"),
                    stage=stage,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    return await asyncio.to_thread(_sync)


async def async_send_command(host: "Host", command: str, *, timeout_ops: float | None = None) -> dict[str, Any] | None:
    """
    异步执行单条命令。

    Args:
        host: Nornir Host 对象
        command: 要执行的命令

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 命令输出
        - elapsed_time: 执行耗时
        - failed: 是否失败
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    device_name = host.data.get("device_name", host.name)

    try:
        response = await _run_send_command(host, kwargs, command, timeout_ops=timeout_ops)
        return {
            "success": not response.failed,
            "result": response.result,
            "elapsed_time": response.elapsed_time,
            "failed": response.failed,
        }
    except ScrapliAuthenticationFailed as e:
        # OTP 认证失败时立即抛出 428，让前端重新输入
        await handle_otp_auth_failure(dict(host.data), e)
        raise  # 满足类型检查
    except ScrapliTimeout as e:
        logger.warning("命令执行超时", host=device_name, command=command, error=str(e))
        raise
    except Exception as e:
        logger.error("命令执行失败", host=device_name, command=command, error=str(e), exc_info=True)
        raise


async def async_send_commands(host: "Host", commands: list[str]) -> dict[str, Any]:
    """
    异步执行多条命令。

    Args:
        host: Nornir Host 对象
        commands: 命令列表

    Returns:
        包含执行结果的字典：
        - success: 是否全部成功
        - results: 各命令输出列表
        - failed_commands: 失败的命令列表
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    device_name = host.data.get("device_name", host.name)

    start = time.monotonic()
    stage = "init"
    safe_first = (commands[0] or "").strip().splitlines()[0][:120] if commands else ""

    def _sync() -> dict[str, Any]:
        nonlocal stage
        conn = Scrapli(**kwargs)
        try:
            stage = "open"
            logger.info("Scrapli 打开连接", host=device_name, device=host.hostname, platform=kwargs.get("platform"))
            conn.open()
            logger.info(
                "Scrapli 连接已打开",
                host=device_name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            stage = "send_commands"
            logger.info(
                "Scrapli 执行多条命令",
                host=device_name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                commands_count=len(commands),
                first_command=safe_first,
            )
            responses: MultiResponse = conn.send_commands(commands)
            logger.info(
                "Scrapli 多命令返回",
                host=device_name,
                device=host.hostname,
                platform=kwargs.get("platform"),
                failed=responses.failed,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            results: list[dict[str, Any]] = []
            failed_commands: list[str] = []
            for cmd, resp in zip(commands, responses, strict=False):
                results.append({"command": cmd, "result": resp.result, "failed": resp.failed})
                if resp.failed:
                    failed_commands.append(cmd)

            return {"success": len(failed_commands) == 0, "results": results, "failed_commands": failed_commands}
        finally:
            try:
                stage = "close"
                conn.close()
                logger.info(
                    "Scrapli 连接已关闭",
                    host=device_name,
                    device=host.hostname,
                    platform=kwargs.get("platform"),
                    stage=stage,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    try:
        return await asyncio.to_thread(_sync)
    except ScrapliAuthenticationFailed as e:
        # OTP 认证失败时立即抛出 428，让前端重新输入
        await handle_otp_auth_failure(dict(host.data), e)
        raise  # 满足类型检查
    except ScrapliTimeout as e:
        logger.warning("批量命令执行超时", host=device_name, stage=stage, error=str(e))
        raise
    except Exception as e:
        logger.error("批量命令执行失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_send_config(host: "Host", config: str | list[str]) -> dict[str, Any]:
    """
    异步下发配置。

    Args:
        host: Nornir Host 对象
        config: 配置内容（字符串或行列表）

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 配置下发输出
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    device_name = host.data.get("device_name", host.name)
    # 配置转为行列表
    if isinstance(config, str):
        config_lines = [line.strip() for line in config.splitlines() if line.strip()]
    else:
        config_lines = config

    try:

        def _sync() -> dict[str, Any]:
            conn = Scrapli(**kwargs)
            try:
                conn.open()
                response: MultiResponse = conn.send_configs(config_lines)
                failed_lines = [r for r in response if r.failed]
                return {
                    "success": len(failed_lines) == 0,
                    "result": "\n".join(r.result for r in response),
                    "failed_count": len(failed_lines),
                }
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error("配置下发失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_get_prompt(host: "Host") -> dict[str, Any]:
    """
    异步获取设备提示符（用于连通性测试）。

    Args:
        host: Nornir Host 对象

    Returns:
        包含提示符的字典：
        - success: 是否成功
        - prompt: 设备提示符
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)

    try:

        def _sync() -> dict[str, Any]:
            conn = Scrapli(**kwargs)
            try:
                conn.open()
                prompt = conn.get_prompt()
                return {"success": True, "prompt": prompt}
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return await asyncio.to_thread(_sync)
    except Exception as e:
        logger.error("获取提示符失败", host=host.name, error=str(e), exc_info=True)
        raise


async def async_collect_config(host: "Host") -> dict[str, Any]:
    """
    异步采集设备运行配置。

    根据设备平台自动选择正确的命令。

    Args:
        host: Nornir Host 对象

    Returns:
        包含配置内容的字典：
        - success: 是否成功
        - config: 配置内容
        - platform: 设备平台
    """
    from app.network.platform_config import get_command, get_platform_for_vendor

    raw_platform = host.platform or "hp_comware"

    platform = get_platform_for_vendor(raw_platform)

    # 使用统一的命令映射
    try:
        command = get_command("backup_config", platform)
    except ValueError:
        command = "show running-config"

    timeout_ops = min(60, int(settings.ASYNC_SSH_TIMEOUT or 60))

    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)

    def _sync() -> dict[str, Any]:
        conn = Scrapli(**kwargs)
        try:
            conn.open()
            prompt = None
            try:
                prompt = conn.get_prompt()
            except Exception:
                pass
            disable_paging(conn, platform)
            output = send_command_with_paging(conn, command, timeout_ops=timeout_ops, prompt=prompt)
            return {"success": True, "config": output, "platform": platform}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        return await asyncio.to_thread(_sync)
    except ScrapliAuthenticationFailed as e:
        # OTP 认证失败时立即抛出 428，让前端重新输入
        await handle_otp_auth_failure(dict(host.data), e)
        raise  # 满足类型检查


async def async_deploy_from_host_data(host: "Host") -> dict[str, Any]:
    """
    异步下发配置（从 host.data['deploy_configs'] 读取）。

    用于批量下发场景，每台设备的配置内容存储在 host.data 中。

    Args:
        host: Nornir Host 对象，data 中需包含 'deploy_configs' 键

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 下发输出
        - device_id: 设备 ID
    """
    device_id = host.data.get("device_id", host.name)
    device_name = host.data.get("device_name", host.name)
    configs: list[str] = host.data.get("deploy_configs", [])  # type: ignore[assignment]

    if not configs:
        return {
            "success": True,
            "result": "无配置需要下发",
            "device_id": device_id,
            "skipped": True,
        }

    try:
        result = await async_send_config(host, configs)
        return {
            "success": result["success"],
            "result": result["result"],
            "device_id": device_id,
            "failed_count": result.get("failed_count", 0),
        }
    except Exception as e:
        logger.error("异步配置下发失败", host=device_name, device_id=device_id, error=str(e), exc_info=True)
        raise
