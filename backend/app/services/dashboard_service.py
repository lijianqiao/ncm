"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dashboard_service.py
@DateTime: 2025-12-30 22:15:00
@Docs: 仪表盘业务逻辑 (Dashboard Service).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_menu import CRUDMenu
from app.crud.crud_role import CRUDRole
from app.crud.crud_user import CRUDUser
from app.models.log import LoginLog, OperationLog
from app.models.user import User
from app.schemas.dashboard import DashboardStats, LoginLogSimple


class DashboardService:
    """仪表盘数据聚合服务。"""

    def __init__(
        self,
        db: AsyncSession,
        user_crud: CRUDUser,
        role_crud: CRUDRole,
        menu_crud: CRUDMenu,
    ):
        self.db = db
        self.user_crud = user_crud
        self.role_crud = role_crud
        self.menu_crud = menu_crud

    # ========== 登录日志统计 ==========

    async def _count_login_by_range(
        self, start: datetime, end: datetime, *, user_id: UUID | None = None
    ) -> int:
        """统计指定时间范围内的登录次数。"""
        stmt = select(func.count(LoginLog.id)).where(
            LoginLog.created_at >= start, LoginLog.created_at < end
        )
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _count_login_today(self) -> int:
        """统计今日登录总数。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        return await self._count_login_by_range(today_start, today_end)

    async def _get_login_trend(self, days: int = 7, *, user_id: UUID | None = None) -> list[dict[str, Any]]:
        """获取近 N 天的登录趋势统计。"""
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

        result = await self.db.execute(stmt)
        return [{"date": str(row.d), "count": row.c} for row in result.all()]

    async def _get_recent_logins(self, limit: int = 10, *, user_id: UUID | None = None) -> list[LoginLog]:
        """获取最近的登录日志。"""
        stmt = select(LoginLog)
        if user_id is not None:
            stmt = stmt.where(LoginLog.user_id == user_id)
        result = await self.db.execute(stmt.order_by(LoginLog.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    # ========== 操作日志统计 ==========

    async def _count_operation_by_range(
        self, start: datetime, end: datetime, *, user_id: UUID | None = None
    ) -> int:
        """统计指定时间范围内的操作日志数量。"""
        stmt = select(func.count(OperationLog.id)).where(
            OperationLog.created_at >= start, OperationLog.created_at <= end
        )
        if user_id is not None:
            stmt = stmt.where(OperationLog.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ========== 仪表盘汇总 ==========

    async def get_summary_stats(self, current_user: User) -> DashboardStats:
        """获取仪表盘首页聚合数据。"""
        # 时间范围
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        # 普通用户：个人维度
        my_today_login_count = await self._count_login_by_range(today_start, today_end, user_id=current_user.id)
        my_today_operation_count = await self._count_operation_by_range(today_start, today_end, user_id=current_user.id)
        my_login_trend = await self._get_login_trend(days=7, user_id=current_user.id)
        my_recent_logins_orm = await self._get_recent_logins(limit=10, user_id=current_user.id)
        my_recent_logins = [LoginLogSimple.model_validate(log) for log in my_recent_logins_orm]

        # 超级管理员：全局统计
        if current_user.is_superuser:
            from app.models.rbac import Menu, Role

            active_users = await self.user_crud.count_active(self.db)
            total_users_res = await self.db.execute(select(func.count(User.id)))
            total_users = total_users_res.scalar_one()

            total_roles_res = await self.db.execute(select(func.count(Role.id)))
            total_roles = total_roles_res.scalar_one()

            total_menus_res = await self.db.execute(select(func.count(Menu.id)))
            total_menus = total_menus_res.scalar_one()

            today_login_count = await self._count_login_today()
            today_operation_count = await self._count_operation_by_range(today_start, today_end)

            login_trend = await self._get_login_trend(days=7)
            recent_logins_orm = await self._get_recent_logins(limit=10)
            recent_logins = [LoginLogSimple.model_validate(log) for log in recent_logins_orm]

            return DashboardStats(
                total_users=total_users,
                active_users=active_users,
                total_roles=total_roles,
                total_menus=total_menus,
                today_login_count=today_login_count,
                today_operation_count=today_operation_count,
                login_trend=login_trend,
                recent_logins=recent_logins,
                my_today_login_count=my_today_login_count,
                my_today_operation_count=my_today_operation_count,
                my_login_trend=my_login_trend,
                my_recent_logins=my_recent_logins,
            )

        return DashboardStats(
            total_users=None,
            active_users=None,
            total_roles=None,
            total_menus=None,
            today_login_count=None,
            today_operation_count=None,
            my_today_login_count=my_today_login_count,
            my_today_operation_count=my_today_operation_count,
            my_login_trend=my_login_trend,
            my_recent_logins=my_recent_logins,
        )
