"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_auth_logout.py
@DateTime: 2026-01-07 00:00:00
@Docs: Logout API Tests.
"""

from httpx import AsyncClient

from app.core.auth_cookies import csrf_cookie_name, csrf_header_name, refresh_cookie_name
from app.core.config import settings


class TestAuthLogout:
    async def test_logout_revokes_refresh_token(self, client: AsyncClient, test_superuser) -> None:
        # 1) login -> get refresh
        resp = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "admin", "password": "Admin@123456"},
        )
        assert resp.status_code == 200
        login_data = resp.json()
        access_token = login_data["access_token"]

        old_refresh = client.cookies.get(refresh_cookie_name())
        csrf = client.cookies.get(csrf_cookie_name())
        assert old_refresh
        assert csrf

        # 2) logout
        resp2 = await client.post(
            f"{settings.API_V1_STR}/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["code"] == 200

        # 3) old refresh should not work
        # httpx 不建议 per-request 传 cookies；这里用 client-level cookie 临时覆盖旧 refresh
        client.cookies.set(refresh_cookie_name(), str(old_refresh), path="/")
        client.cookies.set(csrf_cookie_name(), str(csrf), path="/")
        resp3 = await client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={csrf_header_name(): str(csrf)},
        )
        assert resp3.status_code == 401

    async def test_logout_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(f"{settings.API_V1_STR}/auth/logout")
        assert resp.status_code == 401
