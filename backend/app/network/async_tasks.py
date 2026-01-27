"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: async_tasks.py
@DateTime: 2026-01-14 00:30:00
@Docs: Scrapli 异步任务函数库（使用原生 AsyncScrapli）。

提供通用的异步网络设备操作任务，配合 AsyncRunner 使用。
所有函数都是独立的异步函数，接收 Host 对象并返回执行结果。

注意：本模块使用 Scrapli 原生异步驱动 AsyncScrapli，无需 asyncio.to_thread 包装。
"""

import time
from typing import TYPE_CHECKING, Any

from scrapli import AsyncScrapli
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout
from scrapli.response import MultiResponse, Response

from uuid import UUID

from app.core.config import settings
from app.core.logger import logger
from app.network.otp_utils import handle_otp_auth_failure, resolve_otp_password, wait_and_retry_otp
from app.network.platform_config import get_scrapli_options
from app.network.scrapli_utils import disable_paging_async, send_command_with_paging_async

if TYPE_CHECKING:
    from nornir.core.inventory import Host


def _get_scrapli_kwargs(host: "Host") -> dict[str, Any]:
    """
    从 Nornir Host 对象提取 Scrapli 连接参数。

    使用 platform_config.py 中的统一配置作为基础，
    然后覆盖主机特定的连接信息和超时参数。

    注意：AsyncScrapli 需要使用异步 transport（asyncssh），
    同步 transport（ssh2、paramiko）会导致错误。

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
        # AsyncScrapli 必须使用异步 transport（覆盖 platform_config 中的 ssh2）
        "transport": "asyncssh",
    }
    if platform.startswith("cisco_") and not result.get("auth_secondary"):
        result["auth_secondary"] = result.get("auth_password") or ""

    return result


async def _apply_otp_manual_password(host: "Host", kwargs: dict[str, Any]) -> dict[str, Any]:
    """应用 OTP 密码到 Scrapli 连接参数（使用统一的 OTP 解析逻辑）。"""
    auth_type = host.data.get("auth_type")
    host_data = {"name": host.name, **dict(host.data)}

    otp_password = await resolve_otp_password(auth_type, host_data)
    if otp_password is not None:
        kwargs["auth_password"] = otp_password

    return kwargs


async def _run_send_command(
    host: "Host",
    kwargs: dict[str, Any],
    command: str,
    *,
    timeout_ops: float | None = None,
) -> Response:
    """使用 AsyncScrapli 执行单条命令（原生异步）。"""
    start = time.monotonic()
    safe_command = (command or "").strip().splitlines()[0][:120]
    platform = kwargs.get("platform")

    conn = AsyncScrapli(**kwargs)
    try:
        logger.info("AsyncScrapli 打开连接", host=host.name, device=host.hostname, platform=platform)
        await conn.open()
        logger.info(
            "AsyncScrapli 连接已打开",
            host=host.name,
            device=host.hostname,
            platform=platform,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

        logger.info(
            "AsyncScrapli 发送命令",
            host=host.name,
            device=host.hostname,
            platform=platform,
            command=safe_command,
            timeout_ops=timeout_ops,
        )
        response = await conn.send_command(command, timeout_ops=timeout_ops)
        logger.info(
            "AsyncScrapli 命令返回",
            host=host.name,
            device=host.hostname,
            platform=platform,
            command=safe_command,
            failed=response.failed,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            result_len=len(response.result or ""),
        )
        return response
    finally:
        try:
            await conn.close()
            logger.info(
                "AsyncScrapli 连接已关闭",
                host=host.name,
                device=host.hostname,
                platform=platform,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception:
            pass


async def async_send_command(host: "Host", command: str, *, timeout_ops: float | None = None) -> dict[str, Any] | None:
    """
    异步执行单条命令（使用原生 AsyncScrapli）。

    支持 OTP 断点续传：认证失败时等待新 OTP 并重试。

    Args:
        host: Nornir Host 对象
        command: 要执行的命令
        timeout_ops: 命令超时时间（可选）

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
        # 尝试等待新 OTP 并重试
        auth_type = host.data.get("auth_type")
        if auth_type == "otp_manual":
            dept_id_raw = host.data.get("dept_id")
            device_group = host.data.get("device_group")

            if dept_id_raw and device_group:
                logger.info(
                    "认证失败，等待新 OTP",
                    host=device_name,
                    dept_id=str(dept_id_raw),
                    device_group=device_group,
                )
                new_otp = await wait_and_retry_otp(
                    UUID(str(dept_id_raw)),
                    str(device_group),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
                )
                if new_otp:
                    # 使用新 OTP 重试
                    kwargs["auth_password"] = new_otp
                    response = await _run_send_command(host, kwargs, command, timeout_ops=timeout_ops)
                    return {
                        "success": not response.failed,
                        "result": response.result,
                        "elapsed_time": response.elapsed_time,
                        "failed": response.failed,
                    }

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except ScrapliTimeout as e:
        logger.warning("命令执行超时", host=device_name, command=command, error=str(e))
        raise
    except Exception as e:
        logger.error("命令执行失败", host=device_name, command=command, error=str(e), exc_info=True)
        raise


async def async_send_commands(host: "Host", commands: list[str]) -> dict[str, Any]:
    """
    异步执行多条命令（使用原生 AsyncScrapli）。

    支持 OTP 断点续传：认证失败时等待新 OTP 并重试。

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
    platform = kwargs.get("platform")

    async def _execute_commands(connection_kwargs: dict[str, Any]) -> dict[str, Any]:
        """执行命令的内部函数，支持重试。"""
        start = time.monotonic()
        safe_first = (commands[0] or "").strip().splitlines()[0][:120] if commands else ""

        conn = AsyncScrapli(**connection_kwargs)
        try:
            logger.info("AsyncScrapli 打开连接", host=device_name, device=host.hostname, platform=platform)
            await conn.open()
            logger.info(
                "AsyncScrapli 连接已打开",
                host=device_name,
                device=host.hostname,
                platform=platform,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            logger.info(
                "AsyncScrapli 执行多条命令",
                host=device_name,
                device=host.hostname,
                platform=platform,
                commands_count=len(commands),
                first_command=safe_first,
            )
            responses: MultiResponse = await conn.send_commands(commands)
            logger.info(
                "AsyncScrapli 多命令返回",
                host=device_name,
                device=host.hostname,
                platform=platform,
                failed=responses.failed,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            results: list[dict[str, Any]] = []
            failed_commands_list: list[str] = []
            for cmd, resp in zip(commands, responses, strict=False):
                results.append({"command": cmd, "result": resp.result, "failed": resp.failed})
                if resp.failed:
                    failed_commands_list.append(cmd)

            return {"success": len(failed_commands_list) == 0, "results": results, "failed_commands": failed_commands_list}
        finally:
            try:
                await conn.close()
                logger.info(
                    "AsyncScrapli 连接已关闭",
                    host=device_name,
                    device=host.hostname,
                    platform=platform,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    try:
        return await _execute_commands(kwargs)
    except ScrapliAuthenticationFailed as e:
        # 尝试等待新 OTP 并重试
        auth_type = host.data.get("auth_type")
        if auth_type == "otp_manual":
            dept_id_raw = host.data.get("dept_id")
            device_group = host.data.get("device_group")

            if dept_id_raw and device_group:
                logger.info(
                    "认证失败，等待新 OTP",
                    host=device_name,
                    dept_id=str(dept_id_raw),
                    device_group=device_group,
                )
                new_otp = await wait_and_retry_otp(
                    UUID(str(dept_id_raw)),
                    str(device_group),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
                )
                if new_otp:
                    # 使用新 OTP 重试
                    kwargs["auth_password"] = new_otp
                    return await _execute_commands(kwargs)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except ScrapliTimeout as e:
        logger.warning("批量命令执行超时", host=device_name, error=str(e))
        raise
    except Exception as e:
        logger.error("批量命令执行失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_send_config(host: "Host", config: str | list[str]) -> dict[str, Any]:
    """
    异步下发配置（使用原生 AsyncScrapli）。

    支持 OTP 断点续传：认证失败时等待新 OTP 并重试。

    Args:
        host: Nornir Host 对象
        config: 配置内容（字符串或行列表）

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 配置下发输出
        - failed_count: 失败行数
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    device_name = host.data.get("device_name", host.name)
    platform = kwargs.get("platform")

    # 配置转为行列表
    if isinstance(config, str):
        config_lines = [line.strip() for line in config.splitlines() if line.strip()]
    else:
        config_lines = config

    async def _send_config(connection_kwargs: dict[str, Any]) -> dict[str, Any]:
        """执行配置下发的内部函数，支持重试。"""
        start = time.monotonic()
        conn = AsyncScrapli(**connection_kwargs)
        try:
            logger.info("AsyncScrapli 打开连接（配置下发）", host=device_name, device=host.hostname, platform=platform)
            await conn.open()

            response: MultiResponse = await conn.send_configs(config_lines)
            failed_lines = [r for r in response if r.failed]

            logger.info(
                "AsyncScrapli 配置下发完成",
                host=device_name,
                device=host.hostname,
                platform=platform,
                config_lines=len(config_lines),
                failed_count=len(failed_lines),
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            return {
                "success": len(failed_lines) == 0,
                "result": "\n".join(r.result for r in response),
                "failed_count": len(failed_lines),
            }
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    try:
        return await _send_config(kwargs)
    except ScrapliAuthenticationFailed as e:
        # 尝试等待新 OTP 并重试
        auth_type = host.data.get("auth_type")
        if auth_type == "otp_manual":
            dept_id_raw = host.data.get("dept_id")
            device_group = host.data.get("device_group")

            if dept_id_raw and device_group:
                logger.info(
                    "配置下发认证失败，等待新 OTP",
                    host=device_name,
                    dept_id=str(dept_id_raw),
                    device_group=device_group,
                )
                new_otp = await wait_and_retry_otp(
                    UUID(str(dept_id_raw)),
                    str(device_group),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
                )
                if new_otp:
                    # 使用新 OTP 重试
                    kwargs["auth_password"] = new_otp
                    return await _send_config(kwargs)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except Exception as e:
        logger.error("配置下发失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_get_prompt(host: "Host") -> dict[str, Any]:
    """
    异步获取设备提示符（用于连通性测试，使用原生 AsyncScrapli）。

    Args:
        host: Nornir Host 对象

    Returns:
        包含提示符的字典：
        - success: 是否成功
        - prompt: 设备提示符
    """
    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    platform = kwargs.get("platform")

    conn = AsyncScrapli(**kwargs)
    try:
        logger.info("AsyncScrapli 打开连接（获取提示符）", host=host.name, device=host.hostname, platform=platform)
        await conn.open()
        prompt = await conn.get_prompt()
        return {"success": True, "prompt": prompt}
    except Exception as e:
        logger.error("获取提示符失败", host=host.name, error=str(e), exc_info=True)
        raise
    finally:
        try:
            await conn.close()
        except Exception:
            pass


async def async_collect_config(host: "Host") -> dict[str, Any]:
    """
    异步采集设备运行配置（使用原生 AsyncScrapli）。

    根据设备平台自动选择正确的命令。
    支持 OTP 断点续传：认证失败时等待新 OTP 并重试。

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

    async def _collect_config(connection_kwargs: dict[str, Any]) -> dict[str, Any]:
        """执行配置采集的内部函数，支持重试。"""
        start = time.monotonic()
        conn = AsyncScrapli(**connection_kwargs)
        try:
            logger.info("AsyncScrapli 打开连接（配置采集）", host=host.name, device=host.hostname, platform=platform)
            await conn.open()

            # 获取提示符
            prompt = None
            try:
                prompt = await conn.get_prompt()
            except Exception:
                pass

            # 关闭分页
            await disable_paging_async(conn, platform)

            # 采集配置（处理分页）
            output = await send_command_with_paging_async(conn, command, timeout_ops=timeout_ops, prompt=prompt)

            logger.info(
                "AsyncScrapli 配置采集完成",
                host=host.name,
                device=host.hostname,
                platform=platform,
                config_len=len(output or ""),
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            return {"success": True, "config": output, "platform": platform}
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    try:
        return await _collect_config(kwargs)
    except ScrapliAuthenticationFailed as e:
        # 尝试等待新 OTP 并重试
        auth_type = host.data.get("auth_type")
        if auth_type == "otp_manual":
            dept_id_raw = host.data.get("dept_id")
            device_group = host.data.get("device_group")

            if dept_id_raw and device_group:
                logger.info(
                    "配置采集认证失败，等待新 OTP",
                    host=host.name,
                    dept_id=str(dept_id_raw),
                    device_group=device_group,
                )
                new_otp = await wait_and_retry_otp(
                    UUID(str(dept_id_raw)),
                    str(device_group),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
                )
                if new_otp:
                    # 使用新 OTP 重试
                    kwargs["auth_password"] = new_otp
                    return await _collect_config(kwargs)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise


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


async def async_get_lldp_neighbors(host: "Host") -> dict[str, Any]:
    """
    异步获取设备 LLDP 邻居信息（使用原生 AsyncScrapli）。

    根据设备平台自动选择正确的命令，并使用 TextFSM 解析输出。
    支持 OTP 断点续传：认证失败时等待新 OTP 并重试。

    Args:
        host: Nornir Host 对象

    Returns:
        包含 LLDP 邻居信息的字典：
        - success: 是否成功
        - raw: 原始输出
        - parsed: 解析后的结构化数据
        - platform: 设备平台
    """
    from app.network.platform_config import get_command, get_platform_for_vendor
    from app.network.textfsm_parser import parse_command_output

    raw_platform = host.platform or "hp_comware"
    platform = get_platform_for_vendor(raw_platform)

    # 使用统一的命令映射
    try:
        command = get_command("lldp_neighbors", platform)
    except ValueError:
        command = "show lldp neighbors detail"

    kwargs = _get_scrapli_kwargs(host)
    kwargs = await _apply_otp_manual_password(host, kwargs)
    device_name = host.data.get("device_name", host.name)

    async def _collect_lldp(connection_kwargs: dict[str, Any]) -> dict[str, Any]:
        """执行 LLDP 采集的内部函数，支持重试。"""
        start = time.monotonic()
        conn = AsyncScrapli(**connection_kwargs)
        try:
            logger.info("AsyncScrapli 打开连接（LLDP 采集）", host=device_name, device=host.hostname, platform=platform)
            await conn.open()

            response = await conn.send_command(command)

            raw_output = response.result
            parsed = None

            # 使用 TextFSM 解析
            if platform:
                try:
                    parsed = parse_command_output(
                        platform=platform,
                        command=command,
                        output=raw_output,
                    )
                except Exception as e:
                    logger.warning("TextFSM 解析失败", host=device_name, error=str(e))

            logger.info(
                "AsyncScrapli LLDP 采集完成",
                host=device_name,
                device=host.hostname,
                platform=platform,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                parsed_count=len(parsed) if parsed else 0,
            )

            return {
                "success": not response.failed,
                "raw": raw_output,
                "parsed": parsed,
                "platform": platform,
            }
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    try:
        return await _collect_lldp(kwargs)
    except ScrapliAuthenticationFailed as e:
        # 尝试等待新 OTP 并重试
        auth_type = host.data.get("auth_type")
        if auth_type == "otp_manual":
            dept_id_raw = host.data.get("dept_id")
            device_group = host.data.get("device_group")

            if dept_id_raw and device_group:
                logger.info(
                    "LLDP 采集认证失败，等待新 OTP",
                    host=device_name,
                    dept_id=str(dept_id_raw),
                    device_group=device_group,
                )
                new_otp = await wait_and_retry_otp(
                    UUID(str(dept_id_raw)),
                    str(device_group),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS,
                )
                if new_otp:
                    # 使用新 OTP 重试
                    kwargs["auth_password"] = new_otp
                    return await _collect_lldp(kwargs)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except Exception as e:
        logger.error("LLDP 采集失败", host=device_name, error=str(e), exc_info=True)
        raise
