"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: data_scope.py
@DateTime: 2026-01-08 14:25:00
@Docs: 数据权限过滤模块 - 基于 DataScope 枚举实现数据范围控制。
"""

from uuid import UUID

from sqlalchemy import Select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DataScope
from app.crud.crud_dept import CRUDDept
from app.models.user import User


async def get_user_dept_ids(
    db: AsyncSession,
    user: User,
    data_scope: DataScope,
    dept_crud: CRUDDept,
) -> list[UUID] | None:
    """
    根据数据权限范围获取用户可访问的部门 ID 列表。

    Args:
        db: 数据库会话
        user: 当前用户
        data_scope: 数据权限范围
        dept_crud: 部门 CRUD 实例

    Returns:
        可访问的部门 ID 列表，None 表示可访问全部（ALL 或超级管理员）
    """
    # 超级管理员可访问全部
    if user.is_superuser:
        return None

    match data_scope:
        case DataScope.ALL:
            # 全部数据
            return None

        case DataScope.CUSTOM:
            # 自定义权限：根据用户角色关联的部门（暂未实现角色-部门关联，返回本部门）
            # TODO: 实现角色-部门关联后，从关联表获取
            if user.dept_id:
                return [user.dept_id]
            return []

        case DataScope.DEPT:
            # 本部门
            if user.dept_id:
                return [user.dept_id]
            return []

        case DataScope.DEPT_AND_CHILDREN:
            # 本部门及下级
            if not user.dept_id:
                return []
            children = await dept_crud.get_children_ids(db, dept_id=user.dept_id)
            return [user.dept_id] + children

        case DataScope.SELF:
            # 仅本人 - 返回空列表表示只能看自己创建的
            return []

        case _:
            return []


def apply_dept_filter(
    stmt: Select,
    dept_ids: list[UUID] | None,
    user_id: UUID | None = None,
    dept_column=None,
    created_by_column=None,
) -> Select:
    """
    对查询语句应用部门过滤。

    Args:
        stmt: SQLAlchemy Select 语句
        dept_ids: 可访问的部门 ID 列表（None 表示不过滤）
        user_id: 当前用户 ID（用于 SELF 模式）
        dept_column: 部门 ID 列（默认为查询模型的 dept_id）
        created_by_column: 创建者列（用于 SELF 模式回退）

    Returns:
        添加过滤条件后的查询语句
    """
    if dept_ids is None:
        # None 表示可访问全部，不添加过滤
        return stmt

    conditions = []

    if dept_ids:
        # 有可访问的部门
        if dept_column is not None:
            conditions.append(dept_column.in_(dept_ids))

    if user_id and created_by_column is not None:
        # SELF 模式：允许看自己创建的数据
        conditions.append(created_by_column == user_id)

    if not conditions:
        # 没有任何条件，无法访问任何数据（返回 False 条件）
        from sqlalchemy import false

        return stmt.where(false())

    # 使用 OR 组合条件：在部门范围内 OR 自己创建的
    return stmt.where(or_(*conditions))


def get_user_effective_data_scope(user: User) -> DataScope:
    """
    获取用户的有效数据权限范围。

    根据用户所有角色的 data_scope 取最大权限。

    Args:
        user: 用户对象（需要预加载 roles）

    Returns:
        有效的数据权限范围
    """
    if user.is_superuser:
        return DataScope.ALL

    if not user.roles:
        return DataScope.SELF

    # 权限优先级：ALL > CUSTOM > DEPT_AND_CHILDREN > DEPT > SELF
    priority: dict[DataScope, int] = {
        DataScope.ALL: 5,
        DataScope.CUSTOM: 4,
        DataScope.DEPT_AND_CHILDREN: 3,
        DataScope.DEPT: 2,
        DataScope.SELF: 1,
    }

    max_scope = DataScope.SELF
    max_priority = 1

    for role in user.roles:
        if role.is_active and not role.is_deleted:
            # 确保 role.data_scope 转换为 DataScope 枚举
            role_scope = DataScope(role.data_scope) if isinstance(role.data_scope, str) else role.data_scope
            scope_priority = priority.get(role_scope, 1)
            if scope_priority > max_priority:
                max_priority = scope_priority
                max_scope = role_scope

    return max_scope
