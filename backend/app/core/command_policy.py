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
    re.compile(r"^\s*(format|reformat)\b", re.IGNORECASE),
    re.compile(r"^\s*(write\s+erase|erase\s+startup-config)\b", re.IGNORECASE),
    re.compile(r"^\s*(reload|reboot)\b", re.IGNORECASE),
    re.compile(r"^\s*(reset)\b", re.IGNORECASE),
    re.compile(r"^\s*(delete)\s+.*(startup|boot|system)\b", re.IGNORECASE),
    re.compile(r"^\s*(undo)\s+(local-user|super)\b", re.IGNORECASE),
)

# 注意：白名单过严会阻断正常配置。这里给一个“相对安全”的基础集合，
# 若你后续希望更严格，可以在 deploy_plan 里打开严格模式/自定义前缀列表。
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
    """把渲染后的配置文本转换成命令列表（按行）。"""
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
    """校验命令集合是否满足安全策略。"""
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
