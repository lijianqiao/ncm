"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: permissions.py
@DateTime: 2026-01-06 00:00:00
@Docs: 权限码显式注册表（权限码以代码为源）。
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PermissionCode(str, Enum):
    """权限码（必须显式注册，禁止在业务代码中散落魔法字符串）。"""

    USER_LIST = "user:list"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_RECYCLE = "user:recycle"
    USER_RESTORE = "user:restore"
    USER_PASSWORD_RESET = "user:password:reset"

    USER_ROLES_LIST = "user:roles:list"
    USER_ROLES_UPDATE = "user:roles:update"

    MENU_OPTIONS_LIST = "menu:options:list"
    MENU_LIST = "menu:list"
    MENU_CREATE = "menu:create"
    MENU_UPDATE = "menu:update"
    MENU_DELETE = "menu:delete"
    MENU_RECYCLE = "menu:recycle"
    MENU_RESTORE = "menu:restore"

    ROLE_LIST = "role:list"
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_RECYCLE = "role:recycle"
    ROLE_RESTORE = "role:restore"

    ROLE_MENUS_LIST = "role:menus:list"
    ROLE_MENUS_UPDATE = "role:menus:update"

    LOG_LOGIN_LIST = "log:login:list"
    LOG_OPERATION_LIST = "log:operation:list"

    SESSION_LIST = "session:list"
    SESSION_KICK = "session:kick"

    # 部门权限
    DEPT_LIST = "dept:list"
    DEPT_CREATE = "dept:create"
    DEPT_UPDATE = "dept:update"
    DEPT_DELETE = "dept:delete"
    DEPT_RECYCLE = "dept:recycle"
    DEPT_RESTORE = "dept:restore"


@dataclass(frozen=True, slots=True)
class PermissionDef:
    code: PermissionCode
    name: str
    description: str | None = None


PERMISSION_DEFS: tuple[PermissionDef, ...] = (
    PermissionDef(PermissionCode.USER_LIST, "用户-列表"),
    PermissionDef(PermissionCode.USER_CREATE, "用户-创建"),
    PermissionDef(PermissionCode.USER_UPDATE, "用户-更新"),
    PermissionDef(PermissionCode.USER_DELETE, "用户-删除"),
    PermissionDef(PermissionCode.USER_RECYCLE, "用户-回收站"),
    PermissionDef(PermissionCode.USER_RESTORE, "用户-恢复"),
    PermissionDef(PermissionCode.USER_PASSWORD_RESET, "用户-重置密码"),
    PermissionDef(PermissionCode.USER_ROLES_LIST, "用户-角色-列表"),
    PermissionDef(PermissionCode.USER_ROLES_UPDATE, "用户-角色-设置"),
    PermissionDef(PermissionCode.MENU_OPTIONS_LIST, "菜单-可分配选项", "用于获取可分配菜单选项树"),
    PermissionDef(PermissionCode.MENU_LIST, "菜单-列表"),
    PermissionDef(PermissionCode.MENU_CREATE, "菜单-创建"),
    PermissionDef(PermissionCode.MENU_UPDATE, "菜单-更新"),
    PermissionDef(PermissionCode.MENU_DELETE, "菜单-删除"),
    PermissionDef(PermissionCode.MENU_RECYCLE, "菜单-回收站"),
    PermissionDef(PermissionCode.MENU_RESTORE, "菜单-恢复"),
    PermissionDef(PermissionCode.ROLE_LIST, "角色-列表"),
    PermissionDef(PermissionCode.ROLE_CREATE, "角色-创建"),
    PermissionDef(PermissionCode.ROLE_UPDATE, "角色-更新"),
    PermissionDef(PermissionCode.ROLE_DELETE, "角色-删除"),
    PermissionDef(PermissionCode.ROLE_RECYCLE, "角色-回收站"),
    PermissionDef(PermissionCode.ROLE_RESTORE, "角色-恢复"),
    PermissionDef(PermissionCode.ROLE_MENUS_LIST, "角色-菜单-列表"),
    PermissionDef(PermissionCode.ROLE_MENUS_UPDATE, "角色-菜单-设置"),
    PermissionDef(PermissionCode.LOG_LOGIN_LIST, "登录日志-列表"),
    PermissionDef(PermissionCode.LOG_OPERATION_LIST, "操作日志-列表"),
    PermissionDef(PermissionCode.SESSION_LIST, "在线会话-列表"),
    PermissionDef(PermissionCode.SESSION_KICK, "在线会话-强制下线"),
    PermissionDef(PermissionCode.DEPT_LIST, "部门-列表"),
    PermissionDef(PermissionCode.DEPT_CREATE, "部门-创建"),
    PermissionDef(PermissionCode.DEPT_UPDATE, "部门-更新"),
    PermissionDef(PermissionCode.DEPT_DELETE, "部门-删除"),
    PermissionDef(PermissionCode.DEPT_RECYCLE, "部门-回收站"),
    PermissionDef(PermissionCode.DEPT_RESTORE, "部门-恢复"),
)


def list_permission_defs() -> list[PermissionDef]:
    return list(PERMISSION_DEFS)


def validate_no_magic_permission_strings() -> None:
    """启动期校验：禁止在 endpoints 中直接写权限码字符串。

    规则：如果发现 require_permissions([...]) 的入参列表里出现字符串字面量，则认为违规。
    通过强制使用 PermissionCode 显式注册表，避免权限码散落、改名不可控。

    Raises:
        RuntimeError: 发现违规用法时。
    """

    endpoints_dir = Path(__file__).resolve().parents[1] / "api" / "v1" / "endpoints"
    if not endpoints_dir.exists():
        return

    pattern = re.compile(r"require_permissions\s*\(\s*\[\s*['\"]", re.MULTILINE | re.DOTALL)
    violations: list[str] = []

    for py_file in sorted(endpoints_dir.glob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            # 读取失败时不强行阻塞启动（避免环境/编码问题导致不可用）
            continue

        if pattern.search(content):
            violations.append(str(py_file))

    if violations:
        details = "\n".join(f"- {p}" for p in violations)
        raise RuntimeError(
            "检测到 require_permissions 中存在权限码字符串字面量（禁止魔法字符串）。\n"
            "请改为使用 PermissionCode.<...>.value。\n"
            f"违规文件：\n{details}"
        )
