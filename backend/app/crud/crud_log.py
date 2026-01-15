"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_log.py
@DateTime: 2025-12-30 14:40:00
@Docs: 日志 CRUD 操作 (Log CRUD).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.crud.base import CRUDBase
from app.models.log import LoginLog, OperationLog
from app.schemas.log import LoginLogCreate, OperationLogCreate


class CRUDLoginLog(CRUDBase[LoginLog, LoginLogCreate, LoginLogCreate]):
    @staticmethod
    def _apply_keyword_filter(stmt, *, keyword: str | None):
        kw = CRUDBase._normalize_keyword(keyword)
        if not kw:
            return stmt

        clauses = []

        # 文本字段：用户名、IP、提示信息、操作系统
        text_clause = CRUDBase._or_ilike_contains(kw, [LoginLog.username, LoginLog.ip, LoginLog.msg, LoginLog.os])
        if text_clause is not None:
            clauses.append(text_clause)

        # 状态（成功/失败）
        status_true = {"成功", "success", "true", "是", "1"}
        status_false = {"失败", "fail", "false", "否", "0"}
        status_clause = CRUDBase._bool_clause_from_keyword(
            kw, LoginLog.status, true_values=status_true, false_values=status_false
        )
        if status_clause is not None:
            clauses.append(status_clause)

        return stmt.where(or_(*clauses))

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[LoginLog], int]:
        page, page_size = self._validate_pagination(page, page_size)

        count_stmt = select(func.count(LoginLog.id))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(LoginLog)
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(LoginLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_today(self, db: AsyncSession) -> int:
        """
        统计今日登录次数。

        Args:
            db (AsyncSession): 数据库会话。

        Returns:
            int: 今日登录总数。
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        return await self.count_by_range(db, today_start, today_end)

    async def count_by_range(self, db: AsyncSession, start: Any, end: Any, *, user_id: UUID | None = None) -> int:
        """
        统计指定时间范围内的登录次数。

        Args:
            db (AsyncSession): 数据库会话。
            start (Any): 开始时间。
            end (Any): 结束时间。

        Returns:
            int: 该时间段内的登录总数。
        """
        stmt = select(func.count(LoginLog.id)).where(LoginLog.created_at >= start, LoginLog.created_at < end)
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one()

    async def count_by_range_and_user(self, db: AsyncSession, start: Any, end: Any, *, user_id: UUID) -> int:
        """统计指定时间范围内某个用户的登录次数。"""
        return await self.count_by_range(db, start, end, user_id=user_id)

    async def count_today_by_user(self, db: AsyncSession, *, user_id: UUID) -> int:
        """统计某个用户的今日登录次数。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        return await self.count_by_range(db, today_start, today_end, user_id=user_id)

    async def get_trend(self, db: AsyncSession, days: int = 7, *, user_id: UUID | None = None) -> list[dict[str, Any]]:
        """
        获取近 N 天的登录趋势统计。

        基于日期进行聚合统计，用于图表展示。

        Args:
            db (AsyncSession): 数据库会话。
            days (int): 统计天数，默认为 7 天。

        Returns:
            list[dict[str, Any]]: 包含日期和计数的字典列表，例如:
            [{"date": "2023-10-01", "count": 10}, ...]
        """
        # 计算日期范围 (过去 N-1 天 + 今天)
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)

        # 构造跨数据库通用的 Group By Date 查询
        # SQLite/Postgres 都支持 sqlalchemy.cast(..., Date)
        date_col = cast(LoginLog.created_at, Date)

        stmt = (
            select(date_col.label("d"), func.count().label("c"))
            .where(date_col >= start_date)
            .group_by(date_col)
            .order_by(date_col.asc())
        )
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)

        try:
            result = await db.execute(stmt)
            return [{"date": str(row.d), "count": row.c} for row in result.all()]
        except Exception as e:
            logger.error(f"获取登录趋势失败: {e}")
            return []

    async def get_trend_by_user(self, db: AsyncSession, *, user_id: UUID, days: int = 7) -> list[dict[str, Any]]:
        return await self.get_trend(db, days=days, user_id=user_id)

    async def get_recent(self, db: AsyncSession, limit: int = 10, *, user_id: UUID | None = None) -> list[LoginLog]:
        """
        获取最近的登录日志。

        Args:
            db (AsyncSession): 数据库会话。
            limit (int): 返回条数限制，默认为 10。

        Returns:
            list[LoginLog]: 最近的登录日志列表。
        """
        stmt = select(LoginLog)
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await db.execute(stmt.order_by(LoginLog.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_recent_by_user(self, db: AsyncSession, *, user_id: UUID, limit: int = 10) -> list[LoginLog]:
        return await self.get_recent(db, limit=limit, user_id=user_id)


class CRUDOperationLog(CRUDBase[OperationLog, OperationLogCreate, OperationLogCreate]):
    @staticmethod
    def _apply_keyword_filter(stmt, *, keyword: str | None):
        kw = CRUDBase._normalize_keyword(keyword)
        if not kw:
            return stmt

        clauses = []

        # 文本字段：操作人、模块、IP、请求方法
        text_clause = CRUDBase._or_ilike_contains(
            kw, [OperationLog.username, OperationLog.module, OperationLog.ip, OperationLog.method]
        )
        if text_clause is not None:
            clauses.append(text_clause)

        # 状态码：keyword 是纯数字时，按 response_code 精确匹配
        if kw.isdigit():
            clauses.append(OperationLog.response_code == int(kw))

        return stmt.where(or_(*clauses))

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[OperationLog], int]:
        page, page_size = self._validate_pagination(page, page_size)

        count_stmt = select(func.count(OperationLog.id))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(OperationLog)
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(OperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_by_range(self, db: AsyncSession, start: Any, end: Any, *, user_id: UUID | None = None) -> int:
        """
        统计指定时间范围内的操作日志数量。

        Args:
            db (AsyncSession): 数据库会话。
            start (Any): 开始时间。
            end (Any): 结束时间。

        Returns:
            int: 该时间段内的操作日志总数。
        """
        stmt = select(func.count(OperationLog.id)).where(
            OperationLog.created_at >= start, OperationLog.created_at <= end
        )
        if user_id is not None:
            stmt = stmt.where(OperationLog.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one()

    async def count_by_range_and_user(self, db: AsyncSession, start: Any, end: Any, *, user_id: UUID) -> int:
        """统计指定时间范围内某个用户的操作日志数量。"""
        return await self.count_by_range(db, start, end, user_id=user_id)


login_log = CRUDLoginLog(LoginLog)
operation_log = CRUDOperationLog(OperationLog)
