"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_dashboard_service.py
@DateTime: 2025-12-30 22:30:00
@Docs: Dashboard Service Tests.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.dashboard import DashboardStats
from app.services.dashboard_service import DashboardService


class TestDashboardService:
    async def test_get_summary_stats_superuser(
        self,
        db_session: AsyncSession,
        dashboard_service: DashboardService,
        test_superuser: User,
    ):
        stats = await dashboard_service.get_summary_stats(current_user=test_superuser)

        assert isinstance(stats, DashboardStats)
        assert stats.total_users is not None and stats.total_users >= 0
        assert stats.total_roles is not None and stats.total_roles >= 0
        assert stats.total_menus is not None and stats.total_menus >= 0
        assert isinstance(stats.login_trend, list)
        assert isinstance(stats.recent_logins, list)

        assert stats.my_today_login_count >= 0
        assert stats.my_today_operation_count >= 0
        assert isinstance(stats.my_login_trend, list)
        assert isinstance(stats.my_recent_logins, list)

    async def test_get_summary_stats_normal_user(
        self,
        db_session: AsyncSession,
        dashboard_service: DashboardService,
        test_user: User,
    ):
        stats = await dashboard_service.get_summary_stats(current_user=test_user)

        assert isinstance(stats, DashboardStats)
        assert stats.total_users is None
        assert stats.active_users is None
        assert stats.total_roles is None
        assert stats.total_menus is None

        assert stats.my_today_login_count >= 0
        assert stats.my_today_operation_count >= 0
        assert isinstance(stats.my_login_trend, list)
        assert isinstance(stats.my_recent_logins, list)
