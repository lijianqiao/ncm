"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 18:20:00
@Docs: 自定义 TextFSM 模板加载器（自动发现）。

用于加载自定义模板，扩展 ntc-templates 不支持的命令。
模板文件命名规则：{platform}_{command}.textfsm
- 命令中的空格用下划线替换
- 命令中的竖线 | 用 _pipe_ 替换
- 例如：hp_comware_display_version.textfsm
- 例如：juniper_junos_show_configuration_pipe_display_set.textfsm

模块加载时自动扫描目录并注册所有 .textfsm 文件。
"""

import re
from functools import lru_cache
from pathlib import Path

from app.core.logger import logger

# 自定义模板目录
TEMPLATES_DIR = Path(__file__).parent

# 自定义模板注册表（模块加载时自动填充）
CUSTOM_TEMPLATES: dict[str, str] = {}


def _normalize_command_for_key(command: str) -> str:
    """
    将命令标准化为模板键格式。

    转换规则：
    - 空格 → 下划线
    - | → _pipe_
    - 连续下划线 → 单个下划线
    - 全部小写

    Args:
        command: 原始命令

    Returns:
        str: 标准化后的命令键
    """
    normalized = command.lower().strip()
    normalized = normalized.replace("|", "_pipe_")
    normalized = normalized.replace(" ", "_")
    # 移除连续下划线
    normalized = re.sub(r"_+", "_", normalized)
    # 移除首尾下划线
    normalized = normalized.strip("_")
    return normalized


def _parse_template_filename(filename: str) -> tuple[str, str] | None:
    """
    从模板文件名解析平台和命令。

    文件名格式：{platform}_{command}.textfsm
    例如：hp_comware_display_version.textfsm

    Args:
        filename: 模板文件名（不含路径）

    Returns:
        tuple[str, str] | None: (平台, 命令键) 或 None
    """
    if not filename.endswith(".textfsm"):
        return None

    # 移除扩展名
    name = filename[:-8]  # 移除 ".textfsm"

    # 已知平台前缀列表（按长度降序排列，确保优先匹配最长的）
    known_platforms = [
        "juniper_junos",
        "cisco_iosxe",
        "cisco_nxos",
        "arista_eos",
        "huawei_vrp",
        "hp_comware",
        "cisco_ios",
    ]

    for platform in known_platforms:
        if name.startswith(f"{platform}_"):
            command_key = name[len(platform) + 1 :]  # +1 for underscore
            return platform, command_key

    return None


def _discover_templates() -> dict[str, str]:
    """
    扫描模板目录，自动发现并注册所有 .textfsm 文件。

    Returns:
        dict[str, str]: {模板键: 文件路径} 字典
    """
    templates: dict[str, str] = {}

    if not TEMPLATES_DIR.exists():
        logger.warning("TextFSM 模板目录不存在", path=str(TEMPLATES_DIR))
        return templates

    for file_path in TEMPLATES_DIR.glob("*.textfsm"):
        parsed = _parse_template_filename(file_path.name)
        if parsed:
            platform, command_key = parsed
            template_key = f"{platform}_{command_key}"
            templates[template_key] = str(file_path)
            logger.debug("发现 TextFSM 模板", key=template_key, path=file_path.name)

    if templates:
        logger.info("TextFSM 模板自动发现完成", count=len(templates))

    return templates


def _build_template_key(platform: str, command: str) -> str:
    """构建模板查找键。"""
    command_key = _normalize_command_for_key(command)
    return f"{platform}_{command_key}"


@lru_cache(maxsize=256)
def get_template_path(platform: str, command: str) -> str | None:
    """
    获取自定义模板路径（带缓存）。

    Args:
        platform: ntc-templates 平台标识 (hp_comware, huawei_vrp 等)
        command: 原始命令 (如 "display version")

    Returns:
        str | None: 模板文件路径，不存在则返回 None
    """
    template_key = _build_template_key(platform, command)

    if template_key in CUSTOM_TEMPLATES:
        template_path = CUSTOM_TEMPLATES[template_key]
        if Path(template_path).exists():
            return template_path

    # 尝试不同的命令变体（处理命令参数差异）
    # 例如 "display interface GigabitEthernet1/0/1" → "display interface"
    command_parts = command.split()
    for i in range(len(command_parts), 0, -1):
        partial_command = " ".join(command_parts[:i])
        partial_key = _build_template_key(platform, partial_command)
        if partial_key in CUSTOM_TEMPLATES:
            template_path = CUSTOM_TEMPLATES[partial_key]
            if Path(template_path).exists():
                return template_path

    return None


def list_custom_templates() -> list[dict[str, str]]:
    """
    列出所有已注册的自定义模板。

    Returns:
        list[dict]: 模板信息列表，每项包含 key, platform, command, path
    """
    result = []
    for key, path in CUSTOM_TEMPLATES.items():
        parsed = _parse_template_filename(Path(path).name)
        if parsed:
            platform, command_key = parsed
            result.append({
                "key": key,
                "platform": platform,
                "command_key": command_key,
                "path": path,
                "exists": Path(path).exists(),
            })
    return result


def reload_templates() -> int:
    """
    重新扫描并加载模板（用于动态添加模板后刷新）。

    Returns:
        int: 加载的模板数量
    """
    global CUSTOM_TEMPLATES
    CUSTOM_TEMPLATES = _discover_templates()
    # 清除缓存
    get_template_path.cache_clear()
    return len(CUSTOM_TEMPLATES)


def register_template(platform: str, command: str, path: str) -> None:
    """
    手动注册模板（用于测试或动态添加）。

    Args:
        platform: 平台标识
        command: 命令
        path: 模板文件路径
    """
    template_key = _build_template_key(platform, command)
    CUSTOM_TEMPLATES[template_key] = path
    # 清除相关缓存
    get_template_path.cache_clear()
    logger.debug("手动注册 TextFSM 模板", key=template_key, path=path)


# ===== 模块加载时自动发现模板 =====
CUSTOM_TEMPLATES = _discover_templates()
