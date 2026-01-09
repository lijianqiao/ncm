"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_dashboard.py
@DateTime: 2025-12-30 22:30:00
@Docs: Dashboard API Tests.
"""

from httpx import AsyncClient

from app.core.config import settings


class TestDashboard:
    async def test_get_dashboard_summary(self, client: AsyncClient, auth_headers: dict):
        response = await client.get(f"{settings.API_V1_STR}/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "total_users" in data["data"]
        assert "login_trend" in data["data"]
