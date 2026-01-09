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
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 部门关联
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_dept.id"), nullable=True, index=True, comment="所属部门ID"
    )
    dept: Mapped["Department | None"] = relationship("Department", back_populates="users")

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary="sys_user_role", back_populates="users", lazy="selectin"
    )
