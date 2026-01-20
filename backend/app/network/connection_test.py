"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: connection_test.py
@DateTime: 2026-01-09 18:10:00
@Docs: 设备连接测试工具 (Device Connection Test Utility).

用于测试 SSH 连接、验证凭据、获取设备基本信息。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from scrapli import Scrapli
from scrapli.exceptions import (
    ScrapliAuthenticationFailed,
    ScrapliConnectionError,
    ScrapliConnectionNotOpened,
    ScrapliTimeout,
)

from app.core.config import settings
from app.core.logger import logger
from app.network.platform_config import (
    detect_vendor_from_version,
    get_command,
    get_platform_for_vendor,
    get_scrapli_options,
)
from app.network.scrapli_utils import disable_paging, is_command_error, send_command_with_paging


@dataclass
class ConnectionTestResult:
    """连接测试结果。"""

    success: bool
    message: str
    device_info: dict[str, Any] | None = None
    error_type: str | None = None


async def test_device_connection(
    host: str,
    username: str,
    password: str,
    platform: str = "hp_comware",
    port: int = 22,
    timeout: int = 30,
) -> ConnectionTestResult:
    """
    测试单台设备 SSH 连接。

    Args:
        host: 设备 IP 地址或主机名
        username: SSH 用户名
        password: SSH 密码
        platform: Scrapli 平台 (hp_comware, huawei_vrp, cisco_iosxe 等)
        port: SSH 端口
        timeout: 连接超时时间（秒）

    Returns:
        ConnectionTestResult: 连接测试结果
    """
    logger.info(
        "开始设备连接测试",
        host=host,
        platform=platform,
        port=port,
    )

    def _sync() -> ConnectionTestResult:
        scrapli_options = get_scrapli_options(platform)
        scrapli_options["timeout_socket"] = timeout
        scrapli_options["timeout_transport"] = timeout

        device_config = {
            "host": host,
            "auth_username": username,
            "auth_password": password,
            "port": port,
            "platform": platform,
            **scrapli_options,
        }

        try:
            with Scrapli(**device_config) as conn:
                device_info: dict[str, Any] = {
                    "host": host,
                    "platform": platform,
                    "port": port,
                }

                try:
                    version_cmd = get_command("version", platform)
                    response = conn.send_command(version_cmd)
                    if response.failed:
                        logger.warning("获取版本信息失败", host=host, error=response.result)
                    else:
                        device_info["version_output"] = response.result[:500]
                        detected_vendor = detect_vendor_from_version(response.result)
                        if detected_vendor:
                            device_info["detected_vendor"] = detected_vendor
                except Exception as e:
                    logger.warning("获取版本信息异常", host=host, error=str(e))

                logger.info("设备连接测试成功", host=host, platform=platform)

                return ConnectionTestResult(
                    success=True,
                    message="连接成功",
                    device_info=device_info,
                )
        except ScrapliAuthenticationFailed as e:
            logger.warning("设备认证失败", host=host, error=str(e))
            return ConnectionTestResult(success=False, message="认证失败: 用户名或密码错误", error_type="auth_failed")
        except ScrapliTimeout as e:
            logger.warning("设备连接超时", host=host, timeout=timeout, error=str(e))
            return ConnectionTestResult(success=False, message=f"连接超时: {timeout}秒内未响应", error_type="timeout")
        except ScrapliConnectionError as e:
            logger.warning("设备连接错误", host=host, error=str(e))
            return ConnectionTestResult(success=False, message=f"连接错误: {str(e)}", error_type="connection_error")
        except Exception as e:
            logger.error("设备连接测试异常", host=host, error=str(e), exc_info=True)
            return ConnectionTestResult(success=False, message=f"未知错误: {str(e)}", error_type="unknown")

    return await asyncio.to_thread(_sync)


async def test_device_connection_by_vendor(
    host: str,
    username: str,
    password: str,
    vendor: str = "h3c",
    port: int = 22,
    timeout: int = 30,
) -> ConnectionTestResult:
    """
    根据厂商测试设备连接（自动映射平台）。

    Args:
        host: 设备 IP 地址或主机名
        username: SSH 用户名
        password: SSH 密码
        vendor: 设备厂商 (h3c, huawei, cisco 等)
        port: SSH 端口
        timeout: 连接超时时间（秒）

    Returns:
        ConnectionTestResult: 连接测试结果
    """
    platform = get_platform_for_vendor(vendor)
    return await test_device_connection(
        host=host,
        username=username,
        password=password,
        platform=platform,
        port=port,
        timeout=timeout,
    )


async def execute_command_on_device(
    host: str,
    username: str,
    password: str,
    command: str,
    platform: str = "hp_comware",
    port: int = 22,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    在设备上执行单条命令。

    Args:
        host: 设备 IP 地址或主机名
        username: SSH 用户名
        password: SSH 密码
        command: 要执行的命令
        platform: Scrapli 平台
        port: SSH 端口
        timeout: 命令执行超时时间（秒）
     disable_paging(conn, platform)
    Returns:
        dict: 执行结果 {"success": bool, "output": str, "error": str | None}
    """

    def _is_cisco_backup_command(cmd: str, plat: str) -> bool:
        if not str(plat).startswith("cisco_"):
            return False
        cmd_norm = (cmd or "").strip().lower()
        return cmd_norm in {"show running-config", "show run"}

    def _build_device_config(timeout_ops: int) -> dict[str, Any]:
        scrapli_options = get_scrapli_options(platform)
        base_timeout_transport = int(scrapli_options.get("timeout_transport") or 0)
        base_timeout_socket = int(scrapli_options.get("timeout_socket") or 0)
        effective_timeout_ops = max(int(timeout_ops), int(settings.ASYNC_SSH_TIMEOUT or 0))

        scrapli_options["timeout_transport"] = max(base_timeout_transport, effective_timeout_ops)
        scrapli_options["timeout_socket"] = max(
            base_timeout_socket,
            int(settings.ASYNC_SSH_CONNECT_TIMEOUT),
            effective_timeout_ops,
        )
        scrapli_options["timeout_ops"] = effective_timeout_ops

        device_config = {
            "host": host,
            "auth_username": username,
            "auth_password": password,
            "port": port,
            "platform": platform,
            **scrapli_options,
        }
        if platform.startswith("cisco_") and not device_config.get("auth_secondary"):
            device_config["auth_secondary"] = password
        return device_config

    start = time.monotonic()
    stage = "init"
    safe_command = (command or "").strip().splitlines()[0][:120]

    def _sync(device_config: dict[str, Any], timeout_ops: int, attempt: int) -> dict[str, Any]:
        nonlocal stage
        conn = Scrapli(**device_config)
        try:
            logger.info(
                "Scrapli 执行开始",
                host=host,
                platform=platform,
                port=port,
                timeout_socket=device_config.get("timeout_socket"),
                timeout_transport=device_config.get("timeout_transport"),
                timeout_ops=timeout_ops,
                command=safe_command,
                attempt=attempt,
            )

            stage = "open"
            logger.info("Scrapli 打开连接", host=host, platform=platform)
            conn.open()
            logger.info(
                "Scrapli 连接已打开", host=host, platform=platform, elapsed_ms=int((time.monotonic() - start) * 1000)
            )

            stage = "prompt"
            prompt = conn.get_prompt()
            logger.info("Scrapli 获取提示符", host=host, platform=platform, prompt=prompt)

            stage = "disable_paging"
            disable_paging(conn, platform)

            stage = "send_command"
            logger.info("Scrapli 发送命令", host=host, platform=platform, command=safe_command)
            output = send_command_with_paging(conn, command, timeout_ops=timeout_ops, prompt=prompt)
            logger.info(
                "Scrapli 命令返回",
                host=host,
                platform=platform,
                command=safe_command,
                failed=is_command_error(output),
                elapsed_ms=int((time.monotonic() - start) * 1000),
                result_len=len(output or ""),
            )

            if is_command_error(output):
                return {"success": False, "output": "", "error": f"命令执行失败: {output}"}

            return {"success": True, "output": output, "error": None}
        except ScrapliAuthenticationFailed as e:
            logger.warning("设备认证失败", host=host, platform=platform, error=str(e))
            raise
        except ScrapliTimeout as e:
            logger.warning("设备执行超时", host=host, platform=platform, stage=stage, timeout=timeout_ops, error=str(e))
            return {"success": False, "output": "", "error": f"命令执行超时: {e}"}
        except ScrapliConnectionNotOpened as e:
            logger.warning("设备连接未打开", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接未打开: {e}"}
        except ScrapliConnectionError as e:
            logger.warning("设备连接错误", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接错误: {e}"}
        except Exception as e:
            logger.error("设备命令执行异常", host=host, platform=platform, error=str(e), exc_info=True)
            return {"success": False, "output": "", "error": str(e)}
        finally:
            try:
                stage = "close"
                conn.close()
                logger.info(
                    "Scrapli 连接已关闭",
                    host=host,
                    platform=platform,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    base_timeout_ops = max(int(timeout), int(settings.ASYNC_SSH_TIMEOUT or 0))
    retry_timeout_ops = max(base_timeout_ops * 2, base_timeout_ops + 120)
    timeout_candidates = [base_timeout_ops]
    is_cisco_backup_cmd = _is_cisco_backup_command(command, platform)
    if is_cisco_backup_cmd:
        timeout_candidates.append(retry_timeout_ops)

    last_result: dict[str, Any] | None = None
    for idx, timeout_ops in enumerate(timeout_candidates, start=1):
        device_config = _build_device_config(timeout_ops)
        last_result = await asyncio.to_thread(_sync, device_config, timeout_ops, idx)
        if last_result.get("success"):
            return last_result

        error_text = str(last_result.get("error") or "")
        if not is_cisco_backup_cmd:
            return last_result

        if "timed out" not in error_text and "超时" not in error_text:
            return last_result

    return last_result or {"success": False, "output": "", "error": "命令执行失败"}


async def execute_commands_on_device(
    host: str,
    username: str,
    password: str,
    commands: list[str],
    *,
    platform: str = "hp_comware",
    port: int = 22,
    timeout: int = 120,
    is_config: bool = False,
) -> dict[str, Any]:
    """在设备上执行命令列表。

    - 查看类：默认只执行第一条；若传入多条则依次执行并拼接输出。
    - 配置类：使用 scrapli 的 send_configs 逐条下发（模板里应包含进入/退出配置视图的命令）。

    Returns:
        dict: {"success": bool, "output": str, "error": str | None}
    """
    safe_commands = [c.strip() for c in (commands or []) if isinstance(c, str) and c.strip()]
    if not safe_commands:
        return {"success": False, "output": "", "error": "命令为空"}

    scrapli_options = get_scrapli_options(platform)
    base_timeout_transport = int(scrapli_options.get("timeout_transport") or 0)
    scrapli_options["timeout_transport"] = max(base_timeout_transport, timeout)
    base_timeout_socket = int(scrapli_options.get("timeout_socket") or 0)
    scrapli_options["timeout_socket"] = max(base_timeout_socket, int(settings.ASYNC_SSH_CONNECT_TIMEOUT))

    device_config = {
        "host": host,
        "auth_username": username,
        "auth_password": password,
        "port": port,
        "platform": platform,
        **scrapli_options,
    }
    if platform.startswith("cisco_") and not device_config.get("auth_secondary"):
        device_config["auth_secondary"] = password

    start = time.monotonic()
    stage = "init"
    safe_first = safe_commands[0][:120] if safe_commands else ""
    logger.info(
        "Scrapli 执行开始",
        host=host,
        platform=platform,
        port=port,
        timeout_socket=device_config.get("timeout_socket"),
        timeout_transport=device_config.get("timeout_transport"),
        timeout_ops=timeout,
        commands_count=len(safe_commands),
        first_command=safe_first,
        is_config=is_config,
    )

    def _sync_commands() -> dict[str, Any]:
        nonlocal stage
        conn = Scrapli(**device_config)
        try:
            stage = "open"
            logger.info("Scrapli 打开连接", host=host, platform=platform)
            conn.open()
            logger.info(
                "Scrapli 连接已打开", host=host, platform=platform, elapsed_ms=int((time.monotonic() - start) * 1000)
            )

            stage = "prompt"
            prompt = conn.get_prompt()
            logger.info("Scrapli 获取提示符", host=host, platform=platform, prompt=prompt)

            stage = "disable_paging"
            disable_paging(conn, platform)

            if is_config:
                stage = "send_configs"
                logger.info("Scrapli 下发配置", host=host, platform=platform, commands_count=len(safe_commands))
                response = conn.send_configs(safe_commands, timeout_ops=timeout)
                logger.info(
                    "Scrapli 配置返回",
                    host=host,
                    platform=platform,
                    failed=response.failed,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    result_len=len(response.result or ""),
                )
                if response.failed:
                    return {"success": False, "output": "", "error": f"配置下发失败: {response.result}"}
                return {"success": True, "output": response.result, "error": None}

            if len(safe_commands) == 1:
                stage = "send_command"
                logger.info("Scrapli 发送命令", host=host, platform=platform, command=safe_first)
                response = conn.send_command(safe_commands[0], timeout_ops=timeout)
                logger.info(
                    "Scrapli 命令返回",
                    host=host,
                    platform=platform,
                    command=safe_first,
                    failed=response.failed,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                    result_len=len(response.result or ""),
                )
                if response.failed:
                    return {"success": False, "output": "", "error": f"命令执行失败: {response.result}"}
                return {"success": True, "output": response.result, "error": None}

            stage = "send_commands"
            logger.info("Scrapli 执行多条命令", host=host, platform=platform, commands_count=len(safe_commands))
            response = conn.send_commands(safe_commands, timeout_ops=timeout)
            logger.info(
                "Scrapli 多命令返回",
                host=host,
                platform=platform,
                failed=response.failed,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                result_len=len(response.result or ""),
            )
            if response.failed:
                return {"success": False, "output": "", "error": f"命令执行失败: {response.result}"}
            return {"success": True, "output": response.result, "error": None}
        except ScrapliAuthenticationFailed as e:
            logger.warning("设备认证失败", host=host, platform=platform, error=str(e))
            raise
        except ScrapliTimeout as e:
            logger.warning("设备执行超时", host=host, platform=platform, stage=stage, timeout=timeout, error=str(e))
            return {"success": False, "output": "", "error": f"命令执行超时: {e}"}
        except ScrapliConnectionNotOpened as e:
            logger.warning("设备连接未打开", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接未打开: {e}"}
        except ScrapliConnectionError as e:
            logger.warning("设备连接错误", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接错误: {e}"}
        except Exception as e:
            logger.error("设备命令执行异常", host=host, platform=platform, error=str(e), exc_info=True)
            return {"success": False, "output": "", "error": str(e)}
        finally:
            try:
                stage = "close"
                conn.close()
                logger.info(
                    "Scrapli 连接已关闭",
                    host=host,
                    platform=platform,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    return await asyncio.to_thread(_sync_commands)


async def batch_test_connections(
    devices: list[dict[str, Any]],
    concurrency: int = 10,
) -> list[dict[str, Any]]:
    """
    批量测试设备连接。

    Args:
        devices: 设备列表，每个设备包含 host, username, password, platform, port
        concurrency: 并发数

    Returns:
        list[dict]: 测试结果列表
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def test_with_semaphore(device: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            result = await test_device_connection(
                host=device["host"],
                username=device["username"],
                password=device["password"],
                platform=device.get("platform", "hp_comware"),
                port=device.get("port", 22),
            )
            return {
                "host": device["host"],
                "success": result.success,
                "message": result.message,
                "device_info": result.device_info,
                "error_type": result.error_type,
            }

    tasks = [test_with_semaphore(device) for device in devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常结果
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(
                {
                    "host": devices[i]["host"],
                    "success": False,
                    "message": f"测试异常: {str(result)}",
                    "device_info": None,
                    "error_type": "exception",
                }
            )
        else:
            final_results.append(result)

    return final_results


# ===== 同步包装器（便于非异步环境调用）=====


def test_connection_sync(
    host: str,
    username: str,
    password: str,
    platform: str = "hp_comware",
    port: int = 22,
    timeout: int = 30,
) -> ConnectionTestResult:
    """
    同步版本的连接测试（内部使用 asyncio.run）。

    注意：不要在已有事件循环的环境中调用此方法。
    """
    return asyncio.run(
        test_device_connection(
            host=host,
            username=username,
            password=password,
            platform=platform,
            port=port,
            timeout=timeout,
        )
    )
