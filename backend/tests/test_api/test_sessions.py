"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_sessions.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话管理 API Tests.
"""

from httpx import AsyncClient

from app.core.auth_cookies import csrf_cookie_name, csrf_header_name
from app.core.config import settings


class TestSessions:
    async def test_list_online_after_login(self, client: AsyncClient, test_superuser, auth_headers) -> None:
        # 登录后应记录在线
        resp = await client.get(f"{settings.API_V1_STR}/sessions/online", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert any(item["username"] == "admin" for item in data["items"])

    async def test_kick_user_revokes_refresh(self, client: AsyncClient, test_superuser) -> None:
        # 1) login -> get tokens
        resp = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "admin", "password": "Admin@123456"},
        )
        assert resp.status_code == 200
        login_data = resp.json()
        access_token = login_data["access_token"]

        csrf = client.cookies.get(csrf_cookie_name())
        assert csrf

        # 2) kick
        me = await client.get(f"{settings.API_V1_STR}/users/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me.status_code == 200
        user_id = me.json()["data"]["id"]

        kick = await client.post(
            f"{settings.API_V1_STR}/sessions/kick/{user_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert kick.status_code == 200

        # 3) refresh should fail
        resp3 = await client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={csrf_header_name(): str(csrf)},
        )
        assert resp3.status_code == 401
