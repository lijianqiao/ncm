"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: async_tasks.py
@DateTime: 2026-01-14 00:30:00
@Docs: Scrapli 异步任务函数库（使用原生 AsyncScrapli + 连接池）。

提供通用的异步网络设备操作任务，配合 AsyncRunner 使用。
所有函数都是独立的异步函数，接收 Host 对象并返回执行结果。

注意：
- 本模块使用 Scrapli 原生异步驱动 AsyncScrapli
- 使用连接池（AsyncConnectionPool）复用连接，显著提升批量操作性能
"""

import time
from typing import TYPE_CHECKING, Any

from scrapli import AsyncScrapli
from scrapli.exceptions import ScrapliAuthenticationFailed, ScrapliTimeout
from scrapli.response import MultiResponse, Response

from uuid import UUID

from app.core.config import settings
from app.core.logger import logger
from app.network.connection_pool import get_connection_pool
from app.network.otp_utils import handle_otp_auth_failure, resolve_otp_password, wait_and_retry_otp
from app.network.scrapli_utils import build_scrapli_config, disable_paging_async, send_command_with_paging_async

if TYPE_CHECKING:
    from nornir.core.inventory import Host


def _get_scrapli_kwargs(host: "Host") -> dict[str, Any]:
    """
    从 Nornir Host 对象提取 Scrapli 连接参数。

    使用 scrapli_utils.build_scrapli_config 作为统一入口，
    然后添加 AsyncScrapli 特定的配置（asyncssh transport）。

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

    # 从 host 的 connection_options 中获取额外配置
    extras: dict[str, Any] = {}
    if host.connection_options and "scrapli" in host.connection_options:
        extras = host.connection_options["scrapli"].extras or {}

    # 使用统一的配置构建函数
    config = build_scrapli_config(
        host=host.hostname or "",
        username=host.username or "",
        password=host.password or "",
        platform=platform,
        port=host.port or 22,
        extras=extras,
    )

    # AsyncScrapli 必须使用异步 transport（覆盖 platform_config 中的 ssh2）
    config["transport"] = "asyncssh"

    return config


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
    use_pool: bool = True,
) -> Response:
    """使用 AsyncScrapli 执行单条命令（支持连接池复用）。

    Args:
        host: Nornir Host 对象
        kwargs: Scrapli 连接参数
        command: 要执行的命令
        timeout_ops: 命令超时时间
        use_pool: 是否使用连接池（默认 True）

    Returns:
        Response: Scrapli 响应对象
    """
    start = time.monotonic()
    safe_command = (command or "").strip().splitlines()[0][:120]
    platform = kwargs.get("platform")

    if use_pool:
        # 使用连接池
        pool = await get_connection_pool()
        pool_ctx = await pool.acquire(
            host=kwargs["host"],
            username=kwargs["auth_username"],
            password=kwargs["auth_password"],
            platform=platform or "hp_comware",
            port=kwargs.get("port", 22),
            timeout_socket=kwargs.get("timeout_socket"),
            timeout_transport=kwargs.get("timeout_transport"),
            timeout_ops=kwargs.get("timeout_ops"),
            auth_strict_key=kwargs.get("auth_strict_key", False),
            ssh_config_file=kwargs.get("ssh_config_file", ""),
        )
        async with pool_ctx as conn:
            logger.info(
                "连接池获取连接",
                host=host.name,
                device=host.hostname,
                platform=platform,
                reused=pool_ctx.reused,
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
    else:
        # 不使用连接池（用于 OTP 重试等场景）
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
    异步执行单条命令（使用连接池复用连接）。

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
        response = await _run_send_command(host, kwargs, command, timeout_ops=timeout_ops, use_pool=True)
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
                    # 使用新 OTP 重试（不使用连接池，因为密码已变更）
                    kwargs["auth_password"] = new_otp
                    response = await _run_send_command(host, kwargs, command, timeout_ops=timeout_ops, use_pool=False)
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
    异步执行多条命令（使用连接池复用连接）。

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

    async def _execute_commands(connection_kwargs: dict[str, Any], use_pool: bool = True) -> dict[str, Any]:
        """执行命令的内部函数，支持连接池。"""
        start = time.monotonic()
        safe_first = (commands[0] or "").strip().splitlines()[0][:120] if commands else ""

        if use_pool:
            # 使用连接池
            pool = await get_connection_pool()
            pool_ctx = await pool.acquire(
                host=connection_kwargs["host"],
                username=connection_kwargs["auth_username"],
                password=connection_kwargs["auth_password"],
                platform=platform or "hp_comware",
                port=connection_kwargs.get("port", 22),
                timeout_socket=connection_kwargs.get("timeout_socket"),
                timeout_transport=connection_kwargs.get("timeout_transport"),
                timeout_ops=connection_kwargs.get("timeout_ops"),
                auth_strict_key=connection_kwargs.get("auth_strict_key", False),
                ssh_config_file=connection_kwargs.get("ssh_config_file", ""),
            )
            async with pool_ctx as conn:
                logger.info(
                    "连接池获取连接",
                    host=device_name,
                    device=host.hostname,
                    platform=platform,
                    reused=pool_ctx.reused,
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
        else:
            # 不使用连接池
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
                responses = await conn.send_commands(commands)
                logger.info(
                    "AsyncScrapli 多命令返回",
                    host=device_name,
                    device=host.hostname,
                    platform=platform,
                    failed=responses.failed,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

                results = []
                failed_commands_list = []
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
        return await _execute_commands(kwargs, use_pool=True)
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
                    # 使用新 OTP 重试（不使用连接池）
                    kwargs["auth_password"] = new_otp
                    return await _execute_commands(kwargs, use_pool=False)

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
    异步下发配置（使用连接池复用连接）。

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

    async def _send_config(connection_kwargs: dict[str, Any], use_pool: bool = True) -> dict[str, Any]:
        """执行配置下发的内部函数，支持连接池。"""
        start = time.monotonic()

        if use_pool:
            # 使用连接池
            pool = await get_connection_pool()
            pool_ctx = await pool.acquire(
                host=connection_kwargs["host"],
                username=connection_kwargs["auth_username"],
                password=connection_kwargs["auth_password"],
                platform=platform or "hp_comware",
                port=connection_kwargs.get("port", 22),
                timeout_socket=connection_kwargs.get("timeout_socket"),
                timeout_transport=connection_kwargs.get("timeout_transport"),
                timeout_ops=connection_kwargs.get("timeout_ops"),
                auth_strict_key=connection_kwargs.get("auth_strict_key", False),
                ssh_config_file=connection_kwargs.get("ssh_config_file", ""),
            )
            async with pool_ctx as conn:
                logger.info(
                    "连接池获取连接（配置下发）",
                    host=device_name,
                    device=host.hostname,
                    platform=platform,
                    reused=pool_ctx.reused,
                )

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
        else:
            # 不使用连接池
            conn = AsyncScrapli(**connection_kwargs)
            try:
                logger.info("AsyncScrapli 打开连接（配置下发）", host=device_name, device=host.hostname, platform=platform)
                await conn.open()

                response = await conn.send_configs(config_lines)
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
        return await _send_config(kwargs, use_pool=True)
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
                    # 使用新 OTP 重试（不使用连接池）
                    kwargs["auth_password"] = new_otp
                    return await _send_config(kwargs, use_pool=False)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except Exception as e:
        logger.error("配置下发失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_get_prompt(host: "Host") -> dict[str, Any]:
    """
    异步获取设备提示符（用于连通性测试，使用连接池复用连接）。

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

    try:
        # 使用连接池
        pool = await get_connection_pool()
        pool_ctx = await pool.acquire(
            host=kwargs["host"],
            username=kwargs["auth_username"],
            password=kwargs["auth_password"],
            platform=platform or "hp_comware",
            port=kwargs.get("port", 22),
            timeout_socket=kwargs.get("timeout_socket"),
            timeout_transport=kwargs.get("timeout_transport"),
            timeout_ops=kwargs.get("timeout_ops"),
            auth_strict_key=kwargs.get("auth_strict_key", False),
            ssh_config_file=kwargs.get("ssh_config_file", ""),
        )
        async with pool_ctx as conn:
            logger.info(
                "连接池获取连接（获取提示符）",
                host=host.name,
                device=host.hostname,
                platform=platform,
                reused=pool_ctx.reused,
            )
            prompt = await conn.get_prompt()
            return {"success": True, "prompt": prompt}
    except Exception as e:
        logger.error("获取提示符失败", host=host.name, error=str(e), exc_info=True)
        raise


async def async_collect_config(host: "Host") -> dict[str, Any]:
    """
    异步采集设备运行配置（使用连接池复用连接）。

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

    async def _collect_config(connection_kwargs: dict[str, Any], use_pool: bool = True) -> dict[str, Any]:
        """执行配置采集的内部函数，支持连接池。"""
        start = time.monotonic()

        if use_pool:
            # 使用连接池
            pool = await get_connection_pool()
            pool_ctx = await pool.acquire(
                host=connection_kwargs["host"],
                username=connection_kwargs["auth_username"],
                password=connection_kwargs["auth_password"],
                platform=platform,
                port=connection_kwargs.get("port", 22),
                timeout_socket=connection_kwargs.get("timeout_socket"),
                timeout_transport=connection_kwargs.get("timeout_transport"),
                timeout_ops=connection_kwargs.get("timeout_ops"),
                auth_strict_key=connection_kwargs.get("auth_strict_key", False),
                ssh_config_file=connection_kwargs.get("ssh_config_file", ""),
            )
            async with pool_ctx as conn:
                logger.info(
                    "连接池获取连接（配置采集）",
                    host=host.name,
                    device=host.hostname,
                    platform=platform,
                    reused=pool_ctx.reused,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

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
        else:
            # 不使用连接池
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
        return await _collect_config(kwargs, use_pool=True)
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
                    # 使用新 OTP 重试（不使用连接池）
                    kwargs["auth_password"] = new_otp
                    return await _collect_config(kwargs, use_pool=False)

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
    异步获取设备 LLDP 邻居信息（使用连接池复用连接）。

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

    async def _collect_lldp(connection_kwargs: dict[str, Any], use_pool: bool = True) -> dict[str, Any]:
        """执行 LLDP 采集的内部函数，支持连接池。"""
        start = time.monotonic()

        if use_pool:
            # 使用连接池
            pool = await get_connection_pool()
            pool_ctx = await pool.acquire(
                host=connection_kwargs["host"],
                username=connection_kwargs["auth_username"],
                password=connection_kwargs["auth_password"],
                platform=platform,
                port=connection_kwargs.get("port", 22),
                timeout_socket=connection_kwargs.get("timeout_socket"),
                timeout_transport=connection_kwargs.get("timeout_transport"),
                timeout_ops=connection_kwargs.get("timeout_ops"),
                auth_strict_key=connection_kwargs.get("auth_strict_key", False),
                ssh_config_file=connection_kwargs.get("ssh_config_file", ""),
            )
            async with pool_ctx as conn:
                logger.info(
                    "连接池获取连接（LLDP 采集）",
                    host=device_name,
                    device=host.hostname,
                    platform=platform,
                    reused=pool_ctx.reused,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

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
        else:
            # 不使用连接池
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
        return await _collect_lldp(kwargs, use_pool=True)
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
                    # 使用新 OTP 重试（不使用连接池）
                    kwargs["auth_password"] = new_otp
                    return await _collect_lldp(kwargs, use_pool=False)

        # 无法恢复，抛出 OTPRequiredException
        await handle_otp_auth_failure(dict(host.data), e)
        raise
    except Exception as e:
        logger.error("LLDP 采集失败", host=device_name, error=str(e), exc_info=True)
        raise
