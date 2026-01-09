"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: initial_data.py
@DateTime: 2025-12-30 13:05:00
@Docs: 数据初始化脚本 (支持 --reset 重置 和 --init 初始化).
"""

import argparse
import asyncio
import logging
import os
import sys
import tomllib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal, engine
from app.core.enums import DataScope, MenuType
from app.crud.crud_dept import dept_crud
from app.crud.crud_menu import menu as menu_crud
from app.crud.crud_role import role as role_crud
from app.crud.crud_user import user as user_crud

# 确保所有模型被导入，以便 create_all 能识别
from app.models.base import Base
from app.models.dept import Department
from app.models.rbac import Menu, Role
from app.schemas.dept import DeptCreate
from app.schemas.menu import MenuCreate
from app.schemas.role import RoleCreate
from app.schemas.user import UserCreate

RBAC_SEED_PATH = os.path.join(os.path.dirname(__file__), "docs", "rbac_seed.toml")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reset_db() -> None:
    """
    重置数据库：删除所有表。
    """
    logger.warning("正在重置数据库 (删除所有表)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("数据库已重置。")


async def init_db() -> None:
    """
    初始化数据库：创建表并创建超级管理员。
    """
    logger.info("正在初始化数据库 (创建表)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        user = await user_crud.get_by_username(db, username=settings.FIRST_SUPERUSER)
        if not user:
            logger.info(f"正在创建超级管理员: {settings.FIRST_SUPERUSER}")
            user_in = UserCreate(  # pyright: ignore[reportCallIssue]
                username=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                email=settings.FIRST_SUPERUSER_EMAIL,
                phone=settings.FIRST_SUPERUSER_PHONE,
                nickname=settings.FIRST_SUPERUSER_NICKNAME,
                is_superuser=True,
                is_active=True,
                gender=settings.FIRST_SUPERUSER_GENDER,
            )
            await user_crud.create(db, obj_in=user_in)
            await db.commit()
            logger.info("超级管理员创建成功。")
        else:
            logger.info("超级管理员已存在，跳过创建。")

        await init_depts(db)
        await init_rbac(db)


def _to_none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    return v if v else None


def _infer_menu_type(*, permission: str | None, component: str | None) -> MenuType:
    if permission:
        return MenuType.PERMISSION
    if component == "Layout":
        return MenuType.CATALOG
    return MenuType.MENU


async def _get_menu_by_name(db: AsyncSession, *, name: str) -> Menu | None:
    result = await db.execute(select(Menu).where(Menu.name == name))
    return result.scalars().first()


async def _get_role_by_code(db: AsyncSession, *, code: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.code == code))
    return result.scalars().first()


async def _get_dept_by_code(db: AsyncSession, *, code: str) -> Department | None:
    result = await db.execute(select(Department).where(Department.code == code))
    return result.scalars().first()


async def init_depts(db: AsyncSession) -> None:
    """初始化部门数据（幂等）。"""

    if not os.path.exists(RBAC_SEED_PATH):
        logger.warning(f"未找到 RBAC 种子文件，跳过部门初始化: {RBAC_SEED_PATH}")
        return

    with open(RBAC_SEED_PATH, "rb") as f:
        seed = tomllib.load(f)

    depts_seed: list[dict] = seed.get("depts", [])
    if not depts_seed:
        logger.info("未在 rbac_seed.toml 中找到部门数据，跳过部门初始化。")
        return

    logger.info("正在初始化部门数据...")

    # 建立 code -> Department 映射（用于处理父部门）
    code_to_dept: dict[str, Department] = {}

    for d in depts_seed:
        code = str(d.get("code", "")).strip()
        name = str(d.get("name", "")).strip()
        if not code or not name:
            raise ValueError(f"部门缺少 code/name: {d}")

        parent_code = _to_none_if_empty(d.get("parent_code"))
        parent_id: UUID | None = None
        if parent_code:
            parent_dept = code_to_dept.get(parent_code)
            if parent_dept is None:
                raise ValueError(f"部门 parent_code 未找到（请确保父部门在子部门之前定义）: {code} -> {parent_code}")
            parent_id = parent_dept.id

        sort = int(d.get("sort", 0))
        leader = _to_none_if_empty(d.get("leader"))
        phone = _to_none_if_empty(d.get("phone"))
        email = _to_none_if_empty(d.get("email"))

        existing = await _get_dept_by_code(db, code=code)
        if existing:
            existing.name = name
            existing.parent_id = parent_id
            existing.sort = sort
            existing.leader = leader
            existing.phone = phone
            existing.email = email
            existing.is_deleted = False
            existing.is_active = True
            dept_obj = existing
        else:
            dept_obj = await dept_crud.create(
                db,
                obj_in=DeptCreate(
                    name=name,
                    code=code,
                    parent_id=parent_id,
                    sort=sort,
                    leader=leader,
                    phone=phone,
                    email=email,
                ),
            )

        code_to_dept[code] = dept_obj

    await db.commit()
    logger.info("部门数据初始化完成。")


async def init_rbac(db: AsyncSession) -> None:
    """初始化 RBAC 菜单与角色（幂等）。"""

    if not os.path.exists(RBAC_SEED_PATH):
        logger.warning(f"未找到 RBAC 种子文件，跳过初始化: {RBAC_SEED_PATH}")
        return

    logger.info(f"正在初始化 RBAC 菜单/角色: {RBAC_SEED_PATH}")

    with open(RBAC_SEED_PATH, "rb") as f:
        seed = tomllib.load(f)

    menus_seed: list[dict] = seed.get("menus", [])
    roles_seed: list[dict] = seed.get("roles", [])

    # 1) 初始化菜单（支持 parent_key）
    key_to_menu: dict[str, Menu] = {}
    for m in menus_seed:
        key = str(m.get("key", "")).strip()
        if not key:
            raise ValueError("rbac_seed.toml 中存在空的 menus.key")

        title = str(m.get("title", "")).strip()
        name = str(m.get("name", "")).strip()
        if not title or not name:
            raise ValueError(f"菜单缺少 title/name: key={key}")

        parent_key = _to_none_if_empty(m.get("parent_key"))
        parent_id: UUID | None = None
        if parent_key:
            parent_menu = key_to_menu.get(parent_key)
            if parent_menu is None:
                raise ValueError(f"菜单 parent_key 未找到（请确保父菜单在子菜单之前定义）: {key} -> {parent_key}")
            parent_id = parent_menu.id

        path = _to_none_if_empty(m.get("path"))
        component = _to_none_if_empty(m.get("component"))
        icon = _to_none_if_empty(m.get("icon"))
        permission = _to_none_if_empty(m.get("permission"))
        sort = int(m.get("sort", 0))
        is_hidden = bool(m.get("is_hidden", False))
        type_raw = _to_none_if_empty(m.get("type"))
        if type_raw:
            try:
                menu_type = MenuType(str(type_raw))
            except ValueError as e:
                raise ValueError(f"菜单 type 非法: key={key}, type={type_raw}") from e
        else:
            menu_type = _infer_menu_type(permission=permission, component=component)

        existing = await _get_menu_by_name(db, name=name)
        if existing:
            existing.title = title
            existing.parent_id = parent_id
            existing.path = path
            existing.component = component
            existing.icon = icon
            existing.sort = sort
            existing.type = menu_type
            existing.is_hidden = is_hidden
            existing.permission = permission
            existing.is_deleted = False
            existing.is_active = True
            menu_obj = existing
        else:
            menu_obj = await menu_crud.create(
                db,
                obj_in=MenuCreate(
                    title=title,
                    name=name,
                    parent_id=parent_id,
                    path=path,
                    component=component,
                    icon=icon,
                    sort=sort,
                    type=menu_type,
                    is_hidden=is_hidden,
                    permission=permission,
                ),
            )

        key_to_menu[key] = menu_obj

    await db.flush()
    await db.commit()

    # 2) 建立 permission -> Menu 映射
    permission_to_menu_id: dict[str, UUID] = {}
    for menu_obj in key_to_menu.values():
        if menu_obj.permission:
            permission_to_menu_id[menu_obj.permission] = menu_obj.id

    # 3) 初始化角色（按 code 幂等更新菜单绑定）
    for r in roles_seed:
        role_name = str(r.get("name", "")).strip()
        role_code = str(r.get("code", "")).strip()
        if not role_name or not role_code:
            raise ValueError("角色缺少 name/code")

        role_desc = _to_none_if_empty(r.get("description"))
        role_sort = int(r.get("sort", 0))
        permissions: list[str] = list(r.get("permissions", []) or [])
        data_scope_raw = _to_none_if_empty(r.get("data_scope"))
        data_scope: DataScope | None = None
        if data_scope_raw:
            try:
                data_scope = DataScope(str(data_scope_raw))
            except ValueError as e:
                raise ValueError(f"角色 data_scope 非法: code={role_code}, data_scope={data_scope_raw}") from e

        menu_ids: list[UUID] = []
        missing: list[str] = []
        for p in permissions:
            pid = permission_to_menu_id.get(p)
            if pid is None:
                missing.append(p)
            else:
                menu_ids.append(pid)

        if missing:
            logger.warning(f"角色 {role_code} 存在未匹配的权限点（将忽略这些权限）: {missing}")

        existing_role = await _get_role_by_code(db, code=role_code)
        if existing_role:
            existing_role.name = role_name
            existing_role.description = role_desc
            existing_role.sort = role_sort
            if data_scope is not None:
                existing_role.data_scope = data_scope
            existing_role.is_deleted = False
            existing_role.is_active = True
            # 重新绑定 menus
            result = await db.execute(select(Menu).where(Menu.id.in_(menu_ids)))
            existing_role.menus = list(result.scalars().all())
        else:
            new_role = await role_crud.create(
                db,
                obj_in=RoleCreate(
                    name=role_name,
                    code=role_code,
                    description=role_desc,
                    sort=role_sort,
                ),
            )
            if data_scope is not None:
                new_role.data_scope = data_scope
            result = await db.execute(select(Menu).where(Menu.id.in_(menu_ids)))
            new_role.menus = list(result.scalars().all())

    await db.commit()
    logger.info("RBAC 菜单/角色初始化完成。")


def main() -> None:
    parser = argparse.ArgumentParser(description="后台管理系统初始化脚本")
    parser.add_argument("--reset", action="store_true", help="重置数据库 (删除所有数据表)")
    parser.add_argument("--init", action="store_true", help="初始化数据库 (创建表和超级管理员)")

    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset_db())

    if args.init:
        asyncio.run(init_db())

    if not args.reset and not args.init:
        # 默认行为（如果未提供参数，提示用法）
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
