"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2025-12-30 12:10:00
@Docs: 通用 CRUD 仓库基类 (Generic CRUD Repository) - 支持软删除和批量操作。
"""

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base, SoftDeleteMixin

# 定义泛型变量
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase[ModelType: Base, CreateSchemaType: BaseModel, UpdateSchemaType: BaseModel]:
    """
    拥有默认 CRUD 操作的基类。
    支持软删除、乐观锁和批量操作。

    Attributes:
        model (Type[ModelType]): SQLAlchemy 模型类。
    """

    def __init__(self, model: type[ModelType]):
        """
        CRUD 对象初始化。

        Args:
            model (Type[ModelType]): SQLAlchemy 模型类。
        """
        self.model = model

    @staticmethod
    def _normalize_keyword(keyword: str | None) -> str | None:
        """标准化 keyword：strip 后为空则视为 None。"""

        if keyword is None:
            return None
        kw = keyword.strip()
        return kw if kw else None

    @staticmethod
    def _validate_pagination(page: int, page_size: int, max_size: int = 100, default_size: int = 20) -> tuple[int, int]:
        """验证并规范化分页参数。

        Args:
            page: 页码，小于 1 时重置为 1
            page_size: 每页数量，小于 1 时使用默认值，超过 max_size 时截断
            max_size: 允许的最大每页数量
            default_size: 默认每页数量

        Returns:
            tuple[int, int]: 规范化后的 (page, page_size)
        """
        page = max(1, page)
        if page_size < 1:
            page_size = default_size
        page_size = min(page_size, max_size)
        return page, page_size

    @staticmethod
    def _escape_like(value: str) -> str:
        """转义 LIKE/ILIKE 模式中的特殊字符。

        Args:
            value: 原始搜索字符串

        Returns:
            str: 转义后的字符串，可安全用于 LIKE 模式
        """
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    async def get(self, db: AsyncSession, id: UUID) -> ModelType | None:
        """
        通过 ID 获取单个记录。
        """
        query = select(self.model).where(self.model.id == id)  # pyright: ignore[reportAttributeAccessIssue]

        if issubclass(self.model, SoftDeleteMixin):
            query = query.where(self.model.is_deleted.is_(False))

        result = await db.execute(query)
        return result.scalars().first()

    async def count(self, db: AsyncSession) -> int:
        """
        获取记录总数 (支持软删除过滤)。
        """
        query = select(func.count()).select_from(self.model)

        if issubclass(self.model, SoftDeleteMixin):
            query = query.where(self.model.is_deleted.is_(False))

        result = await db.execute(query)
        return result.scalar() or 0

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """
        获取多条记录 (分页)。
        """
        query = select(self.model)

        if issubclass(self.model, SoftDeleteMixin):
            query = query.where(self.model.is_deleted.is_(False))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_multi_paginated(
        self, db: AsyncSession, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[ModelType], int]:
        """
        获取分页数据，返回 (items, total)。

        Args:
            page: 页码 (从 1 开始)
            page_size: 每页大小

        Returns:
            (items, total): 数据列表和总数
        """
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100  # 限制最大每页数量

        total = await self.count(db)
        skip = (page - 1) * page_size
        items = await self.get_multi(db, skip=skip, limit=page_size)
        return items, total

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        创建新记录。
        """
        obj_in_data = obj_in.model_dump(exclude_unset=True)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        """
        更新记录。
        """
        obj_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)

        for field in obj_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, obj_data[field])

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID) -> ModelType | None:
        """
        删除记录 (优先软删除，否则硬删除)。
        """
        obj = await self.get(db, id=id)
        if obj:
            if isinstance(obj, SoftDeleteMixin):
                obj.is_deleted = True
                db.add(obj)
                await db.flush()
                await db.refresh(obj)
            else:
                await db.delete(obj)
                await db.flush()
        return obj

    async def batch_remove(
        self, db: AsyncSession, *, ids: list[UUID], hard_delete: bool = False
    ) -> tuple[int, list[UUID]]:
        """
        批量删除记录。

        Args:
            ids: 要删除的 ID 列表
            hard_delete: 是否硬删除 (默认软删除)

        Returns:
            (success_count, failed_ids): 成功数量和失败的 ID 列表
        """
        success_count = 0
        failed_ids: list[UUID] = []

        # 空列表早返回
        if not ids:
            return success_count, failed_ids

        # 去重
        unique_ids = list(dict.fromkeys(ids))

        # 批量查询所有记录（解决 N+1 问题）
        if hard_delete:
            # 硬删除：包含已软删除的记录
            query = select(self.model).where(
                self.model.id.in_(unique_ids)  # pyright: ignore[reportAttributeAccessIssue]
            )
        else:
            # 软删除：仅查询未删除的记录
            query = select(self.model).where(
                self.model.id.in_(unique_ids)  # pyright: ignore[reportAttributeAccessIssue]
            )
            if issubclass(self.model, SoftDeleteMixin):
                query = query.where(self.model.is_deleted.is_(False))

        result = await db.execute(query)
        objects_map: dict[UUID, ModelType] = {obj.id: obj for obj in result.scalars().all()}  # pyright: ignore[reportAttributeAccessIssue]

        # 处理每条记录
        for id_ in unique_ids:
            obj = objects_map.get(id_)

            if not obj:
                failed_ids.append(id_)
                continue

            try:
                if hard_delete:
                    await db.delete(obj)
                elif isinstance(obj, SoftDeleteMixin):
                    obj.is_deleted = True
                    db.add(obj)
                else:
                    await db.delete(obj)

                success_count += 1
            except Exception as e:
                from app.core.logger import logger

                logger.warning(
                    "批量删除记录失败",
                    record_id=str(id_),
                    model=self.model.__name__,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                failed_ids.append(id_)

        await db.flush()
        return success_count, failed_ids

    async def restore(self, db: AsyncSession, *, id: UUID) -> ModelType | None:
        """
        恢复已软删除的记录。
        """
        # 1. 查找记录 (包括已删除的)
        query = select(self.model).where(self.model.id == id)  # pyright: ignore[reportAttributeAccessIssue]
        result = await db.execute(query)
        obj = result.scalars().first()

        if not obj:
            return None

        # 2. 如果是软删除对象且已删除，则恢复
        if isinstance(obj, SoftDeleteMixin) and obj.is_deleted:
            obj.is_deleted = False
            db.add(obj)
            await db.flush()
            await db.refresh(obj)

        return obj

    async def batch_restore(self, db: AsyncSession, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量恢复软删除的记录。

        Args:
            db: 数据库会话
            ids: 要恢复的记录 ID 列表

        Returns:
            成功恢复数量和失败 ID 列表
        """
        success_count = 0
        failed_ids: list[UUID] = []

        if not ids:
            return success_count, failed_ids

        # 去重
        unique_ids = list(dict.fromkeys(ids))

        # 批量查询所有记录（包括已删除的）
        query = select(self.model).where(
            self.model.id.in_(unique_ids)  # pyright: ignore[reportAttributeAccessIssue]
        )
        result = await db.execute(query)
        objects_map: dict[UUID, ModelType] = {
            obj.id: obj  # pyright: ignore[reportAttributeAccessIssue]
            for obj in result.scalars().all()  # pyright: ignore[reportAttributeAccessIssue]
        }

        # 处理每条记录
        for id_ in unique_ids:
            obj = objects_map.get(id_)

            if not obj:
                failed_ids.append(id_)
                continue

            try:
                if isinstance(obj, SoftDeleteMixin) and obj.is_deleted:
                    obj.is_deleted = False
                    db.add(obj)
                    success_count += 1
                elif isinstance(obj, SoftDeleteMixin) and not obj.is_deleted:
                    # 记录未被删除，视为成功（幂等操作）
                    success_count += 1
                else:
                    # 非软删除模型，无法恢复
                    failed_ids.append(id_)
            except Exception:
                failed_ids.append(id_)

        await db.flush()
        return success_count, failed_ids
