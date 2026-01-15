"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dashboard_service.py
@DateTime: 2025-12-30 22:15:00
@Docs: 仪表盘业务逻辑 (Dashboard Service).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_log import CRUDLoginLog, CRUDOperationLog
from app.crud.crud_menu import CRUDMenu
from app.crud.crud_role import CRUDRole
from app.crud.crud_user import CRUDUser
from app.models.user import User
from app.schemas.dashboard import DashboardStats, LoginLogSimple


class DashboardService:
    """
    仪表盘数据聚合服务。
    """

    def __init__(
        self,
        db: AsyncSession,
        user_crud: CRUDUser,
        role_crud: CRUDRole,
        menu_crud: CRUDMenu,
        login_log_crud: CRUDLoginLog,
        operation_log_crud: CRUDOperationLog,
    ):
        self.db = db
        self.user_crud = user_crud
        self.role_crud = role_crud
        self.menu_crud = menu_crud
        self.login_log_crud = login_log_crud
        self.operation_log_crud = operation_log_crud

    async def get_summary_stats(self, current_user: User) -> DashboardStats:
        """
        获取仪表盘首页聚合数据。
        """
        # 时间范围
        now = datetime.now(UTC).replace(tzinfo=None)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        # 普通用户：个人维度
        my_today_login_count = await self.login_log_crud.count_by_range(
            self.db, today_start, today_end, user_id=current_user.id
        )
        my_today_operation_count = await self.operation_log_crud.count_by_range(
            self.db, today_start, today_end, user_id=current_user.id
        )
        my_login_trend = await self.login_log_crud.get_trend(self.db, days=7, user_id=current_user.id)
        my_recent_logins_orm = await self.login_log_crud.get_recent(self.db, limit=10, user_id=current_user.id)
        my_recent_logins = [LoginLogSimple.model_validate(log) for log in my_recent_logins_orm]

        # 超级管理员：全局统计
        if current_user.is_superuser:
            from sqlalchemy import func, select

            from app.models.rbac import Menu, Role

            active_users = await self.user_crud.count_active(self.db)
            total_users_res = await self.db.execute(select(func.count(User.id)))
            total_users = total_users_res.scalar_one()

            total_roles_res = await self.db.execute(select(func.count(Role.id)))
            total_roles = total_roles_res.scalar_one()

            total_menus_res = await self.db.execute(select(func.count(Menu.id)))
            total_menus = total_menus_res.scalar_one()

            today_login_count = await self.login_log_crud.count_today(self.db)
            today_operation_count = await self.operation_log_crud.count_by_range(self.db, today_start, today_end)

            login_trend = await self.login_log_crud.get_trend(self.db, days=7)
            recent_logins_orm = await self.login_log_crud.get_recent(self.db, limit=10)
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
