"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: rbac.py
@DateTime: 2025-12-30 11:46:00
@Docs: RBAC 相关模型 (角色 Role, 菜单/权限 Menu) 定义。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DataScope, MenuType
from app.models.base import AuditableModel, Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Role(AuditableModel):
    """角色模型。

    系统角色表，用于权限管理和数据权限控制。

    Attributes:
        name (str): 角色名称，唯一。
        code (str): 角色编码，唯一，用于程序识别。
        description (str | None): 角色描述。
        sort (int): 排序权重。
        data_scope (str): 数据权限范围（ALL/CUSTOM/DEPT_AND_CHILDREN/DEPT/SELF）。
        users (list[User]): 拥有此角色的用户列表。
        menus (list[Menu]): 角色关联的菜单/权限列表。
    """

    __tablename__ = "sys_role"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="角色编码")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="描述")
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序权重")
    data_scope: Mapped[str] = mapped_column(
        String(30), default=DataScope.SELF.value, server_default=DataScope.SELF.value, nullable=False, comment="数据权限范围"
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", secondary="sys_user_role", back_populates="roles")
    menus: Mapped[list["Menu"]] = relationship(
        "Menu", secondary="sys_role_menu", back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role(code={self.code}, name={self.name})>"


class Menu(AuditableModel):
    """菜单/权限模型。

    系统菜单和权限表，支持树形结构，用于前端菜单展示和权限控制。

    Attributes:
        title (str): 菜单标题。
        name (str): 前端路由名称。
        parent_id (UUID | None): 父菜单 ID，支持多级菜单。
        path (str | None): 路由路径。
        component (str | None): 前端组件路径。
        icon (str | None): 菜单图标。
        sort (int): 排序权重。
        type (str): 菜单类型（MENU/BUTTON/DIRECTORY）。
        is_hidden (bool): 是否隐藏。
        permission (str | None): 权限标识（如 user:list）。
        children (list[Menu]): 子菜单列表。
        parent (Menu | None): 父菜单对象。
        roles (list[Role]): 拥有此菜单权限的角色列表。
    """

    __tablename__ = "sys_menu"

    title: Mapped[str] = mapped_column(String(50), nullable=False, comment="菜单标题")
    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False, comment="前端路由名称")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_menu.id"), nullable=True, index=True, comment="父菜单ID"
    )
    path: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="路由路径")
    component: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="前端组件路径")
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="菜单图标")
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序权重")
    type: Mapped[str] = mapped_column(String(20), default=MenuType.MENU.value, nullable=False, comment="菜单类型")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否隐藏")
    permission: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="权限标识 (如 user:list)")

    # Relationships
    # 使用 remote_side 指定自关联的远程侧（即父节点侧）
    children: Mapped[list["Menu"]] = relationship("Menu", back_populates="parent", lazy="selectin")
    parent: Mapped[Optional["Menu"]] = relationship("Menu", back_populates="children", remote_side="Menu.id")

    roles: Mapped[list["Role"]] = relationship("Role", secondary="sys_role_menu", back_populates="menus")

    def __repr__(self) -> str:
        return f"<Menu(name={self.name}, title={self.title})>"


class UserRole(Base, UUIDMixin, TimestampMixin):
    """用户-角色关联表。

    多对多关联表，用于建立用户和角色之间的关系。

    Attributes:
        user_id (UUID): 用户 ID。
        role_id (UUID): 角色 ID。
    """

    __tablename__ = "sys_user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_sys_user_role"),
        {"comment": "用户角色关联表"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID"
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID"
    )


class RoleMenu(Base, UUIDMixin, TimestampMixin):
    """角色-菜单关联表。

    多对多关联表，用于建立角色和菜单/权限之间的关系。

    Attributes:
        role_id (UUID): 角色 ID。
        menu_id (UUID): 菜单 ID。
    """

    __tablename__ = "sys_role_menu"
    __table_args__ = (
        UniqueConstraint("role_id", "menu_id", name="uq_sys_role_menu"),
        {"comment": "角色菜单关联表"},
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID"
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_menu.id", ondelete="CASCADE"), nullable=False, index=True, comment="菜单ID"
    )
