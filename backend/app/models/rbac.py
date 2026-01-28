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
    """角色模型。"""

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
    """菜单/权限模型。"""

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
    """用户-角色关联表。"""

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
    """角色-菜单关联表。"""

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
