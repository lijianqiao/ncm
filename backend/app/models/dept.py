"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dept.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门模型 (Department) 定义。
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableModel

if TYPE_CHECKING:
    from app.models.user import User


class Department(AuditableModel):
    """部门模型。"""

    __tablename__ = "sys_dept"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="部门名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False, comment="部门编码")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sys_dept.id"), nullable=True, index=True, comment="父部门ID"
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    leader: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="负责人")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="联系电话")
    email: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="联系邮箱")

    # Relationships - 自关联
    children: Mapped[list["Department"]] = relationship("Department", back_populates="parent", lazy="selectin")
    parent: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="children", remote_side="Department.id"
    )

    # 部门下的用户
    users: Mapped[list["User"]] = relationship("User", back_populates="dept", lazy="selectin")
