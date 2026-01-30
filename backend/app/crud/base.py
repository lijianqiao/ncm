"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2025-12-30 12:10:00
@Docs: 通用 CRUD 仓库基类 (Generic CRUD Repository) - 支持软删除和批量操作。
"""

from collections.abc import Iterable, Sequence
from typing import Any, TypeAlias, TypeVar, cast
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

# 类型别名，减少重复注解
ConditionList: TypeAlias = list[ColumnElement[bool]]


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
        """构建 ILIKE 包含查询条件（不区分大小写）。

        Args:
            column: SQLAlchemy 列对象。
            keyword (str): 搜索关键词。

        Returns:
            ColumnElement[bool]: ILIKE 查询条件。

        Raises:
            ValueError: 当 keyword 为空时。
        """
        kw = cls._normalize_keyword(keyword)
        if not kw:
            raise ValueError("keyword 不能为空")
        escaped = cls._escape_like(kw)
        return column.ilike(f"%{escaped}%", escape="\\")

    @classmethod
    def _or_ilike_contains(cls, keyword: str | None, columns: Sequence[Any]) -> ColumnElement[bool] | None:
        """构建多个列的 OR ILIKE 包含查询条件。

        Args:
            keyword (str | None): 搜索关键词。
            columns (Sequence[Any]): SQLAlchemy 列对象列表。

        Returns:
            ColumnElement[bool] | None: OR ILIKE 查询条件，如果 keyword 为空则返回 None。
        """
        kw = cls._normalize_keyword(keyword)
        if not kw:
            return None
        escaped = cls._escape_like(kw)
        pattern = f"%{escaped}%"
        return or_(*(col.ilike(pattern, escape="\\") for col in columns))

    @staticmethod
    def _and_where(conditions: Iterable[ColumnElement[bool]]) -> ColumnElement[bool]:
        """组合多个条件为 AND 表达式。

        Args:
            conditions: 条件列表

        Returns:
            组合后的 AND 表达式，空列表返回恒真表达式
        """
        conds = list(conditions)
        if not conds:
            return and_(True)  # 空条件返回恒真  # type: ignore[arg-type]
        return and_(*conds)

    @classmethod
    def _parse_bool_keyword(
        cls,
        keyword: str | None,
        *,
        true_values: set[str] | None = None,
        false_values: set[str] | None = None,
    ) -> bool | None:
        """解析关键词为布尔值。

        Args:
            keyword (str | None): 要解析的关键词。
            true_values (set[str] | None): 真值集合，默认为 None（使用默认值）。
            false_values (set[str] | None): 假值集合，默认为 None（使用默认值）。

        Returns:
            bool | None: 解析后的布尔值，如果无法解析则返回 None。
        """
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
        """从关键词构建布尔列查询条件。

        Args:
            keyword (str | None): 要解析的关键词。
            column: SQLAlchemy 布尔列对象。
            true_values (set[str] | None): 真值集合，默认为 None。
            false_values (set[str] | None): 假值集合，默认为 None。

        Returns:
            ColumnElement[bool] | None: 布尔查询条件，如果无法解析则返回 None。
        """
        value = cls._parse_bool_keyword(keyword, true_values=true_values, false_values=false_values)
        if value is None:
            return None
        return column.is_(value)

    def _parse_filter_key(self, key: str) -> tuple[str, str]:
        """解析过滤器键，提取字段名和操作符。

        支持的操作符后缀：
            - __eq: 等于（默认）
            - __ne: 不等于
            - __gt: 大于
            - __gte: 大于等于
            - __lt: 小于
            - __lte: 小于等于
            - __in: 在列表中
            - __not_in: 不在列表中
            - __is: IS（用于布尔/NULL）
            - __is_not: IS NOT
            - __like: LIKE 模式匹配
            - __ilike: ILIKE 模式匹配（不区分大小写）
            - __contains: JSONB 数组包含

        Args:
            key: 过滤器键（如 "status" 或 "created_at__gte"）

        Returns:
            (field_name, operator): 字段名和操作符
        """
        operators = (
            "__gte", "__lte", "__gt", "__lt",
            "__in", "__not_in",
            "__is", "__is_not",
            "__like", "__ilike",
            "__contains",
            "__ne", "__eq",
        )
        for op in operators:
            if key.endswith(op):
                return key[: -len(op)], op[2:]  # 去掉 "__" 前缀
        return key, "eq"

    def _build_filter_condition(self, field_name: str, operator: str, value: Any) -> ColumnElement[bool] | None:
        """根据字段、操作符和值构建过滤条件。

        Args:
            field_name: 字段名
            operator: 操作符（eq, ne, gt, gte, lt, lte, in, not_in, is, is_not, like, ilike, contains）
            value: 过滤值

        Returns:
            SQLAlchemy 条件表达式，或 None（如果值为 None 且操作符不是 is/is_not）
        """
        col = getattr(self.model, field_name, None)
        if col is None:
            return None

        # 对于 is/is_not 操作符，None 是有效值
        if operator not in ("is", "is_not") and value is None:
            return None

        match operator:
            case "eq":
                return col == value
            case "ne":
                return col != value
            case "gt":
                return col > value
            case "gte":
                return col >= value
            case "lt":
                return col < value
            case "lte":
                return col <= value
            case "in":
                if not value:
                    return None
                return col.in_(value)
            case "not_in":
                if not value:
                    return None
                return col.not_in(value)
            case "is":
                return col.is_(value)
            case "is_not":
                return col.is_not(value)
            case "like":
                return col.like(value)
            case "ilike":
                return col.ilike(value)
            case "contains":
                # 用于 JSONB 数组包含查询
                return col.contains(value)
            case _:
                return col == value

    # ========== 核心查询方法 ==========

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> ModelType | None:
        """
        通过 ID 获取单个记录。

        Args:
            db: 数据库会话
            id: 记录 ID
            is_deleted: 软删除过滤（三态参数）
                - False (默认): 只返回未删除记录
                - True: 只返回已删除记录（回收站）
                - None: 返回全部（不过滤删除状态）
            options: 查询选项列表（如 [selectinload(Model.dept)]）

        Returns:
            记录对象或 None
        """
        query = select(self.model).where(self.model.id == id)  # pyright: ignore[reportAttributeAccessIssue]

        # 软删除过滤
        if self._supports_soft_delete and is_deleted is not None:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(is_deleted))

        if options:
            query = query.options(*options)

        result = await db.execute(query)
        return result.scalars().first()

    async def exists(self, db: AsyncSession, id: UUID) -> bool:
        """
        检查记录是否存在（软删除过滤）。

        Args:
            db: 数据库会话
            id: 记录 ID

        Returns:
            记录是否存在
        """
        query = select(func.count()).select_from(self.model).where(
            self.model.id == id  # pyright: ignore[reportAttributeAccessIssue]
        )

        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))

        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def count(self, db: AsyncSession) -> int:
        """获取记录总数（支持软删除过滤）。

        Args:
            db (AsyncSession): 数据库会话。

        Returns:
            int: 记录总数（仅统计未删除的记录）。
        """
        query = select(func.count()).select_from(self.model)

        if self._supports_soft_delete:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(False))

        result = await db.execute(query)
        return result.scalar() or 0

    async def get_by_ids(
        self,
        db: AsyncSession,
        ids: list[UUID],
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> list[ModelType]:
        """
        通过 ID 列表批量获取记录。

        Args:
            db: 数据库会话
            ids: 记录 ID 列表
            is_deleted: 软删除过滤（三态参数）
                - False (默认): 只返回未删除记录
                - True: 只返回已删除记录
                - None: 返回全部（不过滤删除状态）
            options: 查询选项列表（如 [selectinload(Model.dept)]）

        Returns:
            记录列表
        """
        if not ids:
            return []

        query = select(self.model).where(
            self.model.id.in_(ids)  # pyright: ignore[reportAttributeAccessIssue]
        )

        if self._supports_soft_delete and is_deleted is not None:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            query = query.where(soft_model.is_deleted.is_(is_deleted))

        if options:
            query = query.options(*options)

        result = await db.execute(query)
        return list(result.scalars().all())

    # ========== 分页查询方法 ==========

    async def get_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        keyword_columns: Sequence[Any] | None = None,
        order_by: Any | None = None,
        max_size: int = 100,
        options: Sequence[Any] | None = None,
        is_deleted: bool | None = False,
        extra_conditions: Sequence[ColumnElement[bool]] | None = None,
        **filters: Any,
    ) -> tuple[list[ModelType], int]:
        """
        统一分页查询方法（支持搜索、过滤、软删除三态控制）。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键词
            keyword_columns: 关键词搜索的列列表（如 [Model.name, Model.ip]）
            order_by: 排序表达式（如 Model.created_at.desc()）
            max_size: 最大每页数量限制
            options: 查询选项列表（如 [selectinload(Model.dept)]）
            is_deleted: 软删除过滤（三态参数）
                - False (默认): 只返回未删除记录
                - True: 只返回已删除记录（回收站）
                - None: 返回全部记录（不过滤删除状态）
            extra_conditions: 额外的 SQLAlchemy 条件表达式列表（用于复杂查询）
            **filters: 过滤条件，支持以下格式：
                - field=value: 精确匹配（等于）
                - field__ne=value: 不等于
                - field__gt=value: 大于
                - field__gte=value: 大于等于
                - field__lt=value: 小于
                - field__lte=value: 小于等于
                - field__in=[values]: 在列表中
                - field__not_in=[values]: 不在列表中
                - field__is=value: IS（用于布尔/NULL）
                - field__is_not=value: IS NOT
                - field__like=pattern: LIKE 模式匹配
                - field__ilike=pattern: ILIKE（不区分大小写）
                - field__contains=value: JSONB 数组包含

        Returns:
            (items, total): 数据列表和总数

        Example:
            # 正常列表
            items, total = await crud.get_paginated(db, page=1, page_size=20)

            # 回收站
            items, total = await crud.get_paginated(db, is_deleted=True)

            # 带搜索和过滤
            items, total = await crud.get_paginated(
                db,
                keyword="test",
                keyword_columns=[Device.name, Device.ip_address],
                order_by=Device.created_at.desc(),
                options=[selectinload(Device.dept)],
                status="active",
            )

            # 使用操作符过滤
            items, total = await crud.get_paginated(
                db,
                created_at__gte=start_time,        # >= 大于等于
                created_at__lte=end_time,          # <= 小于等于
                status__in=["active", "pending"],  # IN 列表
                is_active__is=True,                # IS 布尔
            )

            # 使用额外条件（复杂查询）
            items, total = await crud.get_paginated(
                db,
                extra_conditions=[
                    Template.vendors.contains([vendor]),  # JSONB 包含
                    or_(Model.a == 1, Model.b == 2),      # 复杂 OR 条件
                ],
            )
        """
        page, page_size = self._validate_pagination(page, page_size, max_size=max_size)

        conditions: ConditionList = []

        # 软删除过滤（三态：False=未删除, True=已删除, None=全部）
        if self._supports_soft_delete and is_deleted is not None:
            soft_model = cast(type[SoftDeleteMixin], self.model)
            conditions.append(soft_model.is_deleted.is_(is_deleted))

        # 关键词搜索
        if keyword and keyword_columns:
            keyword_clause = self._or_ilike_contains(keyword, keyword_columns)
            if keyword_clause is not None:
                conditions.append(keyword_clause)

        # 应用额外条件（SQLAlchemy 表达式）
        if extra_conditions:
            conditions.extend(extra_conditions)

        # 应用过滤条件（支持操作符语法）
        for key, value in filters.items():
            field_name, operator = self._parse_filter_key(key)
            condition = self._build_filter_condition(field_name, operator, value)
            if condition is not None:
                conditions.append(condition)

        where_clause = self._and_where(conditions)

        # 统计总数
        count_stmt = select(func.count(self.model.id)).where(where_clause)  # pyright: ignore[reportAttributeAccessIssue]
        total = await db.scalar(count_stmt) or 0

        # 分页查询
        stmt = select(self.model).where(where_clause)

        # 应用查询选项（selectinload 等）
        if options:
            stmt = stmt.options(*options)

        # 排序
        if order_by is not None:
            # 支持元组排序（如 (Model.sort.asc(), Model.created_at.desc())）
            if isinstance(order_by, tuple):
                stmt = stmt.order_by(*order_by)
            else:
                stmt = stmt.order_by(order_by)
        else:
            # 默认排序：回收站按更新时间，正常列表按创建时间
            if is_deleted is True and hasattr(self.model, "updated_at"):
                stmt = stmt.order_by(self.model.updated_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
            elif hasattr(self.model, "created_at"):
                stmt = stmt.order_by(self.model.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total)

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """创建新记录。

        Args:
            db (AsyncSession): 数据库会话。
            obj_in (CreateSchemaType): 创建数据对象。

        Returns:
            ModelType: 创建后的记录对象。
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
        """更新记录。

        Args:
            db (AsyncSession): 数据库会话。
            db_obj (ModelType): 要更新的记录对象。
            obj_in (UpdateSchemaType | dict[str, Any]): 更新数据对象或字典。

        Returns:
            ModelType: 更新后的记录对象。
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
