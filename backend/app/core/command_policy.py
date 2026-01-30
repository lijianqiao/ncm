"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: command_policy.py
@DateTime: 2026-01-09 23:30:00
@Docs: 配置下发命令安全策略（命令白名单/黑名单）。
"""

import re
from dataclasses import dataclass

from app.core.exceptions import BadRequestException


@dataclass(frozen=True, slots=True)
class CommandPolicy:
    """命令策略（最小可用版本）。"""

    # 危险命令黑名单（出现即拒绝）
    forbidden_patterns: tuple[re.Pattern[str], ...]
    # 允许的命令前缀（可选；为空则仅做黑名单检查）
    allowed_prefixes: tuple[str, ...] = ()


DEFAULT_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 格式化/擦除系统
    re.compile(r"^\s*(format|reformat)\b", re.IGNORECASE),
    re.compile(r"^\s*(write\s+erase|erase\s+startup-config)\b", re.IGNORECASE),
    # 重启/重置设备
    re.compile(r"^\s*(reload|reboot)\b", re.IGNORECASE),
    re.compile(r"^\s*(reset)\b", re.IGNORECASE),
    # 删除启动/系统文件
    re.compile(r"^\s*(delete)\s+.*(startup|boot|system)\b", re.IGNORECASE),
    # 删除本地用户/超级用户
    re.compile(r"^\s*(undo)\s+(local-user|super)\b", re.IGNORECASE),
    # 关机命令
    re.compile(r"^\s*(shutdown)\s*(system|device)?\s*$", re.IGNORECASE),
    # 恢复出厂设置
    re.compile(r"^\s*(restore)\s*(factory-default|default)\b", re.IGNORECASE),
    # 清除安全配置（AAA/SSH/Crypto）
    re.compile(r"^\s*(no\s+)?(crypto|ssh|aaa)\s+.*(delete|remove|clear)\b", re.IGNORECASE),
    # Shell 逃逸命令
    re.compile(r"^\s*(terminal\s+(shell|exec))\b", re.IGNORECASE),
    # H3C 启动配置危险操作
    re.compile(r"^\s*(startup\s+saved-configuration)\s*$", re.IGNORECASE),
    # 清除配置
    re.compile(r"^\s*(clear)\s+(configuration|config|running-config)\b", re.IGNORECASE),
)

# 注意：白名单仅在 strict_allowlist=True 时生效
# 生产环境建议在 deploy_plan 中启用 strict_allowlist 模式以获得更严格的安全保障
DEFAULT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "system-view",
    "return",
    "quit",
    "interface",
    "vlan",
    "vlan-interface",
    "ip",
    "ipv6",
    "ospf",
    "bgp",
    "route-policy",
    "acl",
    "qos",
    "description",
    "undo",
    "snmp-agent",
    "ntp-service",
    "sysname",
)


def normalize_rendered_config(rendered: str) -> list[str]:
    """把渲染后的配置文本转换成命令列表（按行）。

    过滤空行和注释行（以 # 或 ! 开头）。

    Args:
        rendered (str): 渲染后的配置文本。

    Returns:
        list[str]: 命令列表。
    """
    cmds: list[str] = []
    for raw in rendered.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("!"):
            continue
        cmds.append(line)
    return cmds


def validate_commands(
    commands: list[str],
    *,
    strict_allowlist: bool = False,
    policy: CommandPolicy | None = None,
) -> None:
    """校验命令集合是否满足安全策略。

    Args:
        commands (list[str]): 命令列表。
        strict_allowlist (bool): 是否启用严格白名单模式，默认为 False。
        policy (CommandPolicy | None): 命令策略对象，默认为 None（使用默认策略）。

    Returns:
        None: 无返回值。

    Raises:
        BadRequestException: 当命令违反安全策略时。
    """
    p = policy or CommandPolicy(
        forbidden_patterns=DEFAULT_FORBIDDEN_PATTERNS,
        allowed_prefixes=DEFAULT_ALLOWED_PREFIXES,
    )

    violations: list[str] = []
    for cmd in commands:
        for pat in p.forbidden_patterns:
            if pat.search(cmd):
                violations.append(cmd)
                break

        if strict_allowlist and p.allowed_prefixes:
            first = cmd.split(maxsplit=1)[0].lower()
            if first not in {x.lower() for x in p.allowed_prefixes}:
                violations.append(cmd)

    if violations:
        raise BadRequestException(
            message="命令安全策略校验失败，存在危险/不允许的命令",
        )
