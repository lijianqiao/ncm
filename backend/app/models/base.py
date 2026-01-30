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
    """SQLAlchemy 声明式基类。

    所有数据模型的基类，使用统一的元数据命名约定。
    """

    metadata = meta


class TimestampMixin:
    """提供创建时间和更新时间字段的 Mixin。

    自动管理记录的创建时间和更新时间，时间戳带时区信息。
    创建时间在记录插入时自动设置，更新时间在记录修改时自动更新。

    Attributes:
        created_at (datetime): 创建时间，带时区。
        updated_at (datetime): 更新时间，带时区，自动更新。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_func.now(), nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        onupdate=sql_func.now(),
        nullable=False,
        comment="更新时间",
    )


class SoftDeleteMixin:
    """提供软删除标志的 Mixin。

    实现软删除功能，删除记录时不会真正从数据库中删除，
    而是标记为已删除状态，便于数据恢复和审计。

    Attributes:
        is_deleted (bool): 是否已删除，默认为 False。
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, comment="是否已删除"
    )


class UUIDMixin:
    """提供 UUIDv7 主键的 Mixin。

    使用 UUIDv7 作为主键，具有时间排序特性，适合分布式系统。
    UUIDv7 包含时间戳信息，可以按时间顺序排序。

    Attributes:
        id (UUID): 主键 ID，使用 UUIDv7 格式。
    """

    id: Mapped[uuid.UUID] = mapped_column(
        types.Uuid,
        primary_key=True,
        default=uuid6.uuid7,
        unique=True,
        index=True,
        nullable=False,
        comment="主键ID(UUIDv7)",
    )


class VersionMixin:
    """提供乐观锁版本控制的 Mixin。

    实现乐观锁机制，通过版本号字段防止并发更新冲突。
    每次更新记录时，版本号会自动更新，如果版本号不匹配则更新失败。

    Attributes:
        version_id (str): 乐观锁版本号，32 字符的 UUID hex 字符串。
    """

    version_id: Mapped[str] = mapped_column(
        String(32),  # 明确长度为 32 字符（UUID hex）
        default=lambda: uuid.uuid4().hex,
        onupdate=lambda: uuid.uuid4().hex,
        nullable=False,
        comment="乐观锁版本号",
    )

    # 启用 SQLAlchemy 的乐观锁功能
    __mapper_args__ = {
        "version_id_col": version_id,
        "version_id_generator": False,
    }


class AuditableModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    """抽象基础模型，组合以下功能：

    - UUIDv7 主键：使用时间排序的 UUIDv7 作为主键
    - 创建/更新时间戳：自动管理记录的创建和更新时间
    - 软删除标志：支持软删除，便于数据恢复和审计
    - 乐观锁定版本：防止并发更新冲突
    - 启用状态：控制记录是否启用

    所有业务模型应继承此类，以获得完整的审计和版本控制功能。

    Attributes:
        id (UUID): 主键 ID（UUIDv7）。
        created_at (datetime): 创建时间。
        updated_at (datetime): 更新时间。
        is_deleted (bool): 是否已删除。
        version_id (str): 乐观锁版本号。
        is_active (bool): 是否启用。
    """

    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False, comment="是否启用"
    )
