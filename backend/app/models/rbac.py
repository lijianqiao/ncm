"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: rbac.py
@DateTime: 2025-12-30 11:46:00
@Docs: RBAC 相关模型 (角色 Role, 菜单/权限 Menu) 定义。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DataScope, MenuType
from app.models.base import AuditableModel, Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Role(AuditableModel):
    """
    角色模型。
    """

    __tablename__ = "sys_role"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="角色编码")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="描述")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    data_scope: Mapped[DataScope] = mapped_column(
        String(30), default=DataScope.SELF, server_default=DataScope.SELF.value, nullable=False, comment="数据权限范围"
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", secondary="sys_user_role", back_populates="roles")
    menus: Mapped[list["Menu"]] = relationship(
        "Menu", secondary="sys_role_menu", back_populates="roles", lazy="selectin"
    )


class Menu(AuditableModel):
    """
    菜单/权限模型。
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
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    type: Mapped[MenuType] = mapped_column(String(20), default=MenuType.MENU, nullable=False, comment="菜单类型")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否隐藏")
    permission: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="权限标识 (如 user:list)")

    # Relationships
    # 使用 remote_side 指定自关联的远程侧（即父节点侧）
    children: Mapped[list["Menu"]] = relationship("Menu", back_populates="parent", lazy="selectin")
    parent: Mapped[Optional["Menu"]] = relationship("Menu", back_populates="children", remote_side="Menu.id")

    roles: Mapped[list["Role"]] = relationship("Role", secondary="sys_role_menu", back_populates="menus")


class UserRole(Base, UUIDMixin, TimestampMixin):
    """
    用户-角色关联表。

    说明：关联表不需要软删除和乐观锁，简化为基础 Mixin。
    """

    __tablename__ = "sys_user_role"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True
    )


class RoleMenu(Base, UUIDMixin, TimestampMixin):
    """
    角色-菜单关联表。

    说明：关联表不需要软删除和乐观锁，简化为基础 Mixin。
    """

    __tablename__ = "sys_role_menu"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_role.id", ondelete="CASCADE"), nullable=False, index=True
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sys_menu.id", ondelete="CASCADE"), nullable=False, index=True
    )
