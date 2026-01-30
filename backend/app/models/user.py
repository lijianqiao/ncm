"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: user.py
@DateTime: 2025-12-30 11:45:00
@Docs: User model definition.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.dept import Department
    from app.models.rbac import Role


class User(AuditableModel):
    """用户模型。

    系统用户表，存储用户基本信息、认证信息和权限关联。

    Attributes:
        username (str): 用户名，唯一，用于登录。
        password (str): 密码哈希值。
        nickname (str | None): 昵称。
        email (str | None): 邮箱地址，唯一。
        phone (str): 手机号，唯一，用于登录。
        gender (str | None): 性别。
        avatar (str | None): 头像 URL。
        is_superuser (bool): 是否为超级管理员。
        dept_id (UUID | None): 所属部门 ID。
        dept (Department | None): 所属部门对象。
        roles (list[Role]): 用户关联的角色列表。
    """

    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希值")
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="昵称")
    email: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True, comment="邮箱地址")
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False, comment="手机号")
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="性别")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像 URL")

    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否为超级管理员")

    # 部门关联
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_dept.id"), nullable=True, index=True, comment="所属部门ID"
    )
    dept: Mapped["Department | None"] = relationship("Department", back_populates="users")

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary="sys_user_role", back_populates="users", lazy="selectin"
    )
