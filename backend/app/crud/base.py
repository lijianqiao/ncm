"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2025-12-30 12:10:00
@Docs: 通用 CRUD 仓库基类 (Generic CRUD Repository) - 支持软删除和批量操作。
"""

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

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
        self._supports_soft_delete = issubclass(model, SoftDeleteMixin)

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

    @classmethod
    def _ilike_contains(cls, column, keyword: str) -> ColumnElement[bool]:
        kw = cls._normalize_keyword(keyword)
        if not kw:
            raise ValueError("keyword 不能为空")
        escaped = cls._escape_like(kw)
        return column.ilike(f"%{escaped}%", escape="\\")

    @classmethod
    def _or_ilike_contains(cls, keyword: str | None, columns: Sequence[Any]) -> ColumnElement[bool] | None:
        kw = cls._normalize_keyword(keyword)
        if not kw:
            return None
        escaped = cls._escape_like(kw)
        pattern = f"%{escaped}%"
        return or_(*(col.ilike(pattern, escape="\\") for col in columns))

    @staticmethod
    def _and_where(conditions: Iterable[ColumnElement[bool]]) -> ColumnElement[bool]:
        conds = list(conditions)
        return and_(*conds) if conds else and_(True)  # type: ignore[arg-type]

    @classmethod
    def _parse_bool_keyword(
        cls,
        keyword: str | None,
        *,
        true_values: set[str] | None = None,
        false_values: set[str] | None = None,
    ) -> bool | None:
        kw = cls._normalize_keyword(keyword)
        if not kw:
            return None
        normalized = kw.strip().lower()
        t = true_values or {"true", "1", "yes", "y", "是", "对", "开启", "启用", "显示", "hidden"}
        f = false_values or {"false", "0", "no", "n", "否", "错", "关闭", "禁用", "隐藏", "visible"}
        if normalized in {x.lower() for x in t} or kw in t:
            return True
        if normalized in {x.lower() for x in f} or kw in f:
            return False
        return None

    @classmethod
    def _bool_clause_from_keyword(
        cls,
        keyword: str | None,
        column,
        *,
        true_values: set[str] | None = None,
        false_values: set[str] | None = None,
    ) -> ColumnElement[bool] | None:
        value = cls._parse_bool_keyword(keyword, true_values=true_values, false_values=false_values)
        if value is None:
            return None
        return column.is_(value)

    async def paginate(
        self,
        db: AsyncSession,
        *,
        stmt,
        count_stmt,
        page: int = 1,
        page_size: int = 20,
        max_size: int = 100,
        default_size: int = 20,
    ) -> tuple[list[ModelType], int]:
        page, page_size = self._validate_pagination(page, page_size, max_size=max_size, default_size=default_size)
        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        return list(items), int(total)

    async def get(self, db: AsyncSession, id: UUID) -> ModelType | None:
        """
        通过 ID 获取单个记录。
        """
        query = select(self.model).where(self.model.id == id)  # pyright: ignore[reportAttributeAccessIssue]

        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))

        result = await db.execute(query)
        return result.scalars().first()

    async def count(self, db: AsyncSession) -> int:
        """
        获取记录总数 (支持软删除过滤)。
        """
        query = select(func.count()).select_from(self.model)

        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))

        result = await db.execute(query)
        return result.scalar() or 0

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
        page, page_size = self._validate_pagination(page, page_size)

        total = await self.count(db)
        skip = (page - 1) * page_size

        # 内联查询逻辑（原 get_multi）
        query = select(self.model)
        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))
        query = query.offset(skip).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

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
        if not ids:
            return 0, []

        unique_ids = list[UUID](dict.fromkeys(ids))

        existing_stmt = select(self.model.id).where(  # pyright: ignore[reportAttributeAccessIssue]
            self.model.id.in_(unique_ids)  # pyright: ignore[reportAttributeAccessIssue]
        )
        if not hard_delete and self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            existing_stmt = existing_stmt.where(soft_model.is_deleted.is_(False))

        existing_ids = set((await db.execute(existing_stmt)).scalars().all())
        failed_ids = [id_ for id_ in unique_ids if id_ not in existing_ids]
        if not existing_ids:
            return 0, failed_ids

        id_list = list(existing_ids)
        if hard_delete or not self._supports_soft_delete:
            stmt = delete(self.model).where(self.model.id.in_(id_list))  # pyright: ignore[reportAttributeAccessIssue]
        else:
            stmt = (
                update(self.model)  # pyright: ignore[reportAttributeAccessIssue]
                .where(self.model.id.in_(id_list))  # pyright: ignore[reportAttributeAccessIssue]
                .values(is_deleted=True)
            )

        result = await db.execute(stmt)
        await db.flush()
        rowcount = getattr(result, "rowcount", None)
        return int(rowcount or 0), failed_ids

    async def batch_restore(self, db: AsyncSession, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量恢复软删除的记录。

        Args:
            db: 数据库会话
            ids: 要恢复的记录 ID 列表

        Returns:
            成功恢复数量和失败 ID 列表
        """
        if not ids:
            return 0, []

        unique_ids = list(dict.fromkeys(ids))
        if not self._supports_soft_delete:
            return 0, unique_ids

        soft_model = cast(type[SoftDeleteMixin], self.model)
        stmt = select(soft_model.id, soft_model.is_deleted).where(  # pyright: ignore[reportAttributeAccessIssue]
            self.model.id.in_(unique_ids)  # pyright: ignore[reportAttributeAccessIssue]
        )
        rows = (await db.execute(stmt)).all()

        existing_map: dict[UUID, bool] = {row[0]: bool(row[1]) for row in rows}
        existing_ids = set(existing_map.keys())
        failed_ids = [id_ for id_ in unique_ids if id_ not in existing_ids]

        to_restore = [id_ for id_, is_deleted in existing_map.items() if is_deleted]
        if to_restore:
            await db.execute(
                update(self.model)  # pyright: ignore[reportAttributeAccessIssue]
                .where(self.model.id.in_(to_restore))  # pyright: ignore[reportAttributeAccessIssue]
                .values(is_deleted=False)
            )

        await db.flush()
        return len(to_restore), failed_ids

    async def _count_deleted(self, db: AsyncSession) -> int:
        """
        统计已软删除的记录数（内部方法）。

        Returns:
            已删除记录总数，非软删除模型返回 0
        """
        if not self._supports_soft_delete:
            return 0

        soft_model = cast(type[SoftDeleteMixin], self.model)
        result = await db.execute(select(func.count()).select_from(self.model).where(soft_model.is_deleted.is_(True)))
        return result.scalar() or 0

    async def get_multi_by_ids(self, db: AsyncSession, *, ids: list[UUID]) -> list[ModelType]:
        """
        通过 ID 列表批量获取记录。

        Args:
            db: 数据库会话
            ids: 记录 ID 列表

        Returns:
            记录列表
        """
        if not ids:
            return []

        query = select(self.model).where(
            self.model.id.in_(ids)  # pyright: ignore[reportAttributeAccessIssue]
        )

        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_multi_deleted_paginated(
        self, db: AsyncSession, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[ModelType], int]:
        """
        获取已删除记录的分页列表（回收站）。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量

        Returns:
            (items, total): 已删除记录列表和总数
        """
        if not self._supports_soft_delete:
            return [], 0

        page, page_size = self._validate_pagination(page, page_size)

        # 统计总数
        total = await self._count_deleted(db)

        # 分页查询
        skip = (page - 1) * page_size
        soft_model = cast(type[SoftDeleteMixin], self.model)
        query = select(self.model).where(soft_model.is_deleted.is_(True)).offset(skip).limit(page_size)
        result = await db.execute(query)
        return list(result.scalars().all()), total
