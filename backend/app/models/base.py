"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2025-12-30 11:41:00
@Docs: 基础模型定义，包含 UUIDv7 和审计时间戳。
"""

import uuid
from datetime import datetime

import uuid6
from sqlalchemy import Boolean, DateTime, MetaData, String, types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func as sql_func

# 推荐的命名约定
meta = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = meta


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sql_func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        onupdate=sql_func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        types.Uuid,
        primary_key=True,
        default=uuid6.uuid7,
        unique=True,
        index=True,
        nullable=False,
    )


class VersionMixin:
    version_id: Mapped[str] = mapped_column(
        String, default=lambda: uuid.uuid4().hex, onupdate=lambda: uuid.uuid4().hex, nullable=False
    )

    # 启用 SQLAlchemy 的乐观锁功能
    __mapper_args__ = {
        "version_id_col": version_id,
        "version_id_generator": False,
    }


class AuditableModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    """
    抽象基础模型包括：
    - UUIDv7 主键
    - 创建/更新时间戳
    - 软删除标志
    - 乐观锁定版本
    """

    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
