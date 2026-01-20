"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: scrapli_utils.py
@DateTime: 2026-01-19 20:30:00
@Docs: Scrapli 辅助工具（分页处理等）。
"""

import re
from typing import Any

from app.core.logger import logger
from app.network.platform_config import get_paging_disable_commands

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
