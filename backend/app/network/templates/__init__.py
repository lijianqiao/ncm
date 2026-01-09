"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 18:20:00
@Docs: 自定义 TextFSM 模板加载器 (Custom TextFSM Template Loader).

用于加载自定义模板，扩展 ntc-templates 不支持的命令。
"""

from pathlib import Path

# 自定义模板目录
TEMPLATES_DIR = Path(__file__).parent

# 自定义模板注册表
# 格式: {platform}_{command}.textfsm (命令中的空格用下划线替换)
CUSTOM_TEMPLATES: dict[str, str] = {
    # HP Comware (H3C)
    "hp_comware_display_version": str(TEMPLATES_DIR / "hp_comware_display_version.textfsm"),
    "hp_comware_display_lldp_neighbor-information_list": str(
        TEMPLATES_DIR / "hp_comware_display_lldp_neighbor-information_list.textfsm"
    ),
}


def get_template_path(platform: str, command: str) -> str | None:
    """
    获取自定义模板路径。

    Args:
        platform: ntc-templates 平台标识 (hp_comware, huawei_vrp 等)
        command: 原始命令 (如 "display version")

    Returns:
        str | None: 模板文件路径，不存在则返回 None
    """
    # 将命令中的空格替换为下划线，构建模板键
    template_key = f"{platform}_{command.replace(' ', '_')}"

    if template_key in CUSTOM_TEMPLATES:
        template_path = CUSTOM_TEMPLATES[template_key]
        if Path(template_path).exists():
            return template_path

    return None


def list_custom_templates() -> list[str]:
    """列出所有可用的自定义模板。"""
    return list(CUSTOM_TEMPLATES.keys())
