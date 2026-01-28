"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log_service.py
@DateTime: 2025-12-30 12:25:00
@Docs: 日志服务业务逻辑 (Logging Service Logic).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from user_agents import parse

from app.core.decorator import transactional
from app.core.logger import logger
from app.crud.crud_log import CRUDLoginLog, CRUDOperationLog
from app.models.log import LoginLog, OperationLog
from app.schemas.log import LoginLogCreate


class LogService:
    """日志服务类。"""

    # 登录状态关键字映射
    _LOGIN_STATUS_TRUE = {"成功", "success", "true", "是", "1"}
    _LOGIN_STATUS_FALSE = {"失败", "fail", "false", "否", "0"}

    def __init__(self, db: AsyncSession, login_log_crud: CRUDLoginLog, operation_log_crud: CRUDOperationLog):
        self.db = db
        self.login_log_crud = login_log_crud
        self.operation_log_crud = operation_log_crud

    # ========== 登录日志 ==========

    def _build_login_keyword_conditions(self, keyword: str | None) -> list[ColumnElement[bool]]:
        """构建登录日志关键字搜索条件（布尔状态智能匹配）。"""
        if not keyword:
            return []

        kw = keyword.strip().lower()
        if not kw:
            return []

        conditions: list[ColumnElement[bool]] = []

        # 布尔状态智能匹配
        if kw in self._LOGIN_STATUS_TRUE:
            conditions.append(LoginLog.status.is_(True))
        elif kw in self._LOGIN_STATUS_FALSE:
            conditions.append(LoginLog.status.is_(False))

        return conditions

    async def get_login_logs_paginated(
        self, page: int = 1, page_size: int = 20, *, keyword: str | None = None
    ) -> tuple[list[LoginLog], int]:
        """获取分页登录日志列表（支持关键字搜索）。"""
        # 构建额外条件（布尔状态智能匹配）
        extra_conditions = self._build_login_keyword_conditions(keyword)

        return await self.login_log_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            keyword_columns=[LoginLog.username, LoginLog.ip, LoginLog.msg, LoginLog.os],
            order_by=LoginLog.created_at.desc(),
            is_deleted=None,  # 日志不需要软删除过滤
            extra_conditions=extra_conditions if extra_conditions else None,
        )

    async def count_login_today(self) -> int:
        """统计今日登录次数。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        return await self.count_login_by_range(today_start, today_end)

    async def count_login_by_range(
        self, start: datetime, end: datetime, *, user_id: uuid.UUID | None = None
    ) -> int:
        """统计指定时间范围内的登录次数。"""
        stmt = select(func.count(LoginLog.id)).where(
            LoginLog.created_at >= start, LoginLog.created_at < end
        )
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_login_today_by_user(self, user_id: uuid.UUID) -> int:
        """统计某个用户的今日登录次数。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        return await self.count_login_by_range(today_start, today_end, user_id=user_id)

    async def get_login_trend(self, days: int = 7, *, user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        """
        获取近 N 天的登录趋势统计。

        Args:
            days: 统计天数，默认为 7 天。
            user_id: 可选，按用户过滤。

        Returns:
            包含日期和计数的字典列表，如 [{"date": "2023-10-01", "count": 10}, ...]
        """
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)

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
            result = await self.db.execute(stmt)
            return [{"date": str(row.d), "count": row.c} for row in result.all()]
        except Exception as e:
            logger.error(f"获取登录趋势失败: {e}")
            return []

    async def get_recent_logins(self, limit: int = 10, *, user_id: uuid.UUID | None = None) -> list[LoginLog]:
        """获取最近的登录日志。"""
        stmt = select(LoginLog)
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await self.db.execute(stmt.order_by(LoginLog.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    # ========== 操作日志 ==========

    def _build_operation_keyword_conditions(self, keyword: str | None) -> list[ColumnElement[bool]]:
        """构建操作日志关键字搜索条件（状态码数字精确匹配）。"""
        if not keyword:
            return []

        kw = keyword.strip()
        if not kw:
            return []

        conditions: list[ColumnElement[bool]] = []

        # 状态码数字精确匹配
        if kw.isdigit():
            conditions.append(OperationLog.response_code == int(kw))

        return conditions

    async def get_operation_logs_paginated(
        self, page: int = 1, page_size: int = 20, *, keyword: str | None = None
    ) -> tuple[list[OperationLog], int]:
        """获取分页操作日志列表（支持关键字搜索）。"""
        # 构建额外条件（状态码数字精确匹配）
        extra_conditions = self._build_operation_keyword_conditions(keyword)

        return await self.operation_log_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            keyword_columns=[OperationLog.username, OperationLog.module, OperationLog.ip, OperationLog.method],
            order_by=OperationLog.created_at.desc(),
            is_deleted=None,  # 日志不需要软删除过滤
            extra_conditions=extra_conditions if extra_conditions else None,
        )

    async def count_operation_by_range(
        self, start: datetime, end: datetime, *, user_id: uuid.UUID | None = None
    ) -> int:
        """统计指定时间范围内的操作日志数量。"""
        stmt = select(func.count(OperationLog.id)).where(
            OperationLog.created_at >= start, OperationLog.created_at <= end
        )
        if user_id is not None:
            stmt = stmt.where(OperationLog.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ========== 创建日志 ==========

    @transactional()
    async def create_login_log(
        self,
        *,
        user_id: uuid.UUID | str | None = None,
        username: str | None = None,
        request: Request,
        status: bool = True,
        msg: str = "Login Success",
    ) -> LoginLog:
        """创建登录日志。"""
        ip = request.client.host if request.client else None
        ua_string = request.headers.get("user-agent", "")
        user_agent = parse(ua_string)

        # 将 user_id 转为 UUID 对象
        final_user_id: uuid.UUID | None = None
        if user_id:
            if isinstance(user_id, str):
                try:
                    final_user_id = uuid.UUID(user_id)
                except ValueError:
                    final_user_id = None
            else:
                final_user_id = user_id

        log_in = LoginLogCreate(
            user_id=final_user_id,
            username=username,
            ip=ip,
            user_agent=str(user_agent),
            browser=f"{user_agent.browser.family} {user_agent.browser.version_string}",
            os=f"{user_agent.os.family} {user_agent.os.version_string}",
            device=user_agent.device.family,
            status=status,
            msg=msg,
        )

        return await self.login_log_crud.create(self.db, obj_in=log_in)
