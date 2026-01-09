"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: enums.py
@DateTime: 2026-01-06 00:00:00
@Docs: 枚举常量定义（用于替代魔法字符串）。
"""

from enum import Enum


class MenuType(str, Enum):
    """菜单节点类型。"""

    CATALOG = "CATALOG"
    MENU = "MENU"
    PERMISSION = "PERMISSION"


class DataScope(str, Enum):
    """数据权限范围。"""

    ALL = "ALL"  # 全部数据
    CUSTOM = "CUSTOM"  # 自定义（基于角色分配）
    DEPT = "DEPT"  # 本部门
    DEPT_AND_CHILDREN = "DEPT_AND_CHILDREN"  # 本部门及下级
    SELF = "SELF"  # 仅本人
