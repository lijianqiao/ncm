"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: scrapli_utils.py
@DateTime: 2026-01-19 20:30:00
@Docs: Scrapli 辅助工具（配置构建、分页处理等）。
"""

import re
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.network.platform_config import get_paging_disable_commands, get_scrapli_options


def build_scrapli_config(
    host: str,
    username: str,
    password: str,
    platform: str,
    port: int = 22,
    *,
    timeout_socket: int | None = None,
    timeout_transport: int | None = None,
    timeout_ops: int | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    构建 Scrapli 连接配置（统一入口）。

    合并 platform_config 的基础配置、环境变量超时设置、以及调用方的自定义参数。

    Args:
        host: 设备 IP 地址或主机名
        username: SSH 用户名
        password: SSH 密码
        platform: Scrapli 平台标识
        port: SSH 端口
        timeout_socket: Socket 超时（覆盖默认）
        timeout_transport: Transport 超时（覆盖默认）
        timeout_ops: 操作超时（覆盖默认）
        extras: 额外 Scrapli 参数（最高优先级）

    Returns:
        dict: Scrapli 连接配置字典
    """
    # 从 platform_config 获取基础配置
    base_options = get_scrapli_options(platform)

    # 计算有效超时值（取 base、settings、参数中的最大值）
    base_timeout_socket = int(base_options.get("timeout_socket") or 15)
    base_timeout_transport = int(base_options.get("timeout_transport") or 30)
    base_timeout_ops = int(base_options.get("timeout_ops") or 60)

    effective_timeout_socket = max(
        base_timeout_socket,
        int(settings.ASYNC_SSH_CONNECT_TIMEOUT or 30),
        timeout_socket or 0,
    )
    effective_timeout_transport = max(
        base_timeout_transport,
        int(settings.ASYNC_SSH_CONNECT_TIMEOUT or 30),
        timeout_transport or 0,
    )
    effective_timeout_ops = max(
        base_timeout_ops,
        int(settings.ASYNC_SSH_TIMEOUT or 60),
        timeout_ops or 0,
    )

    # 构建配置
    config: dict[str, Any] = {
        **base_options,
        "host": host,
        "auth_username": username,
        "auth_password": password,
        "port": port,
        "platform": platform,
        "timeout_socket": effective_timeout_socket,
        "timeout_transport": effective_timeout_transport,
        "timeout_ops": effective_timeout_ops,
    }

    # Cisco 设备需要 auth_secondary（enable 密码）
    if platform.startswith("cisco_") and not config.get("auth_secondary"):
        config["auth_secondary"] = password

    # 应用额外参数（最高优先级）
    if extras:
        config.update(extras)

    return config

_COMMAND_ERROR_KEYWORDS = [
    "unrecognized command",
    "invalid input",
    "% error",
    "unknown command",
    "incomplete command",
]


def is_command_error(output: str) -> bool:
    """
    判断命令输出是否包含错误关键词。

    Args:
        output: 命令输出

    Returns:
        bool: 是否命令错误
    """
    text = (output or "").lower()
    return any(k in text for k in _COMMAND_ERROR_KEYWORDS)


def disable_paging(conn: Any, platform: str) -> bool:
    """
    尝试关闭分页输出。

    Args:
        conn: Scrapli 连接对象
        platform: Scrapli 平台标识

    Returns:
        bool: 是否成功关闭分页
    """
    commands = get_paging_disable_commands(platform)
    if not commands:
        return False

    for cmd in commands:
        try:
            resp = conn.send_command(cmd, timeout_ops=10)
            if not is_command_error(resp.result or ""):
                return True
        except Exception as e:
            logger.debug("关闭分页命令失败", platform=platform, command=cmd, error=str(e))

    return False


def send_command_with_paging(
    conn: Any,
    command: str,
    *,
    timeout_ops: int,
    more_prompt: str = "More:",
    prompt: str | None = None,
    max_pages: int = 200,
) -> str:
    """
    发送命令并处理分页（More 提示）。

    Args:
        conn: Scrapli 连接对象
        command: 命令
        timeout_ops: 超时秒数
        more_prompt: 分页提示关键词

    Returns:
        str: 命令输出
    """
    output_parts: list[str] = []
    current_input = command
    page_timeout = max(5, min(30, int(timeout_ops)))

    if not prompt:
        try:
            prompt = conn.get_prompt()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("获取提示符失败", error=str(e))
            prompt = None

    expected_outputs: list[str] = [more_prompt]
    if prompt:
        expected_outputs.append(prompt)

    for _ in range(max_pages):
        raw_buf, processed_buf = conn.channel.send_input_and_read(  # type: ignore[attr-defined]
            current_input,
            strip_prompt=True,
            expected_outputs=expected_outputs,
            read_duration=float(timeout_ops if current_input == command else page_timeout),
        )

        text = (processed_buf or b"").decode(errors="ignore")
        output_parts.append(text)

        lower_text = text.lower()
        if prompt and prompt.lower() in lower_text:
            break

        if more_prompt.lower() in lower_text:
            logger.debug("检测到分页提示，继续读取", more_prompt=more_prompt)
            current_input = " "
            continue

        break

    combined = "".join(output_parts)
    return _strip_paging_markers(combined, prompt=prompt)


def _strip_paging_markers(output: str, *, prompt: str | None = None) -> str:
    """
    清理分页提示与多余提示符。

    Args:
        output: 原始输出
        prompt: 设备提示符（可选）

    Returns:
        str: 清理后的输出
    """
    text = output or ""
    text = re.sub(r"More:.*?(\r?\n|$)", "", text, flags=re.IGNORECASE)
    if prompt:
        prompt_pattern = re.escape(prompt)
        text = re.sub(rf"{prompt_pattern}\s*$", "", text)
        text = re.sub(rf"{prompt_pattern}", "", text)
    return text.strip()


# ===== 异步版本（用于 AsyncScrapli）=====


async def disable_paging_async(conn: Any, platform: str) -> bool:
    """
    异步关闭分页输出（用于 AsyncScrapli）。

    Args:
        conn: AsyncScrapli 连接对象
        platform: Scrapli 平台标识

    Returns:
        bool: 是否成功关闭分页
    """
    commands = get_paging_disable_commands(platform)
    if not commands:
        return False

    for cmd in commands:
        try:
            resp = await conn.send_command(cmd, timeout_ops=10)
            if not is_command_error(resp.result or ""):
                return True
        except Exception as e:
            logger.debug("关闭分页命令失败", platform=platform, command=cmd, error=str(e))

    return False


async def send_command_with_paging_async(
    conn: Any,
    command: str,
    *,
    timeout_ops: int,
    more_prompt: str = "More:",
    prompt: str | None = None,
    max_pages: int = 200,
) -> str:
    """
    异步发送命令并处理分页（用于 AsyncScrapli）。

    Args:
        conn: AsyncScrapli 连接对象
        command: 命令
        timeout_ops: 超时秒数
        more_prompt: 分页提示关键词
        prompt: 设备提示符
        max_pages: 最大分页数

    Returns:
        str: 命令输出
    """
    output_parts: list[str] = []
    current_input = command
    page_timeout = max(5, min(30, int(timeout_ops)))

    if not prompt:
        try:
            prompt = await conn.get_prompt()
        except Exception as e:
            logger.debug("获取提示符失败", error=str(e))
            prompt = None

    expected_outputs: list[str] = [more_prompt]
    if prompt:
        expected_outputs.append(prompt)

    for _ in range(max_pages):
        raw_buf, processed_buf = await conn.channel.send_input_and_read(
            current_input,
            strip_prompt=True,
            expected_outputs=expected_outputs,
            read_duration=float(timeout_ops if current_input == command else page_timeout),
        )

        text = (processed_buf or b"").decode(errors="ignore")
        output_parts.append(text)

        lower_text = text.lower()
        if prompt and prompt.lower() in lower_text:
            break

        if more_prompt.lower() in lower_text:
            logger.debug("检测到分页提示，继续读取", more_prompt=more_prompt)
            current_input = " "
            continue

        break

    combined = "".join(output_parts)
    return _strip_paging_markers(combined, prompt=prompt)
