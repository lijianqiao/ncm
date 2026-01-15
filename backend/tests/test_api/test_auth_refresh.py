"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_auth_refresh.py
@DateTime: 2025-12-30 22:40:00
@Docs: Refresh Token API Tests.
"""

import asyncio

from httpx import AsyncClient

from app.core.auth_cookies import csrf_cookie_name, csrf_header_name, refresh_cookie_name
from app.core.config import settings


class TestAuthRefresh:
    async def test_login_returns_refresh_token(self, client: AsyncClient, test_user):
        response = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "testuser", "password": "Test@123456"},
        )
        assert response.status_code == 200
        body = response.json()
        data = body["data"] if isinstance(body, dict) and "data" in body else body
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # refresh_token 应通过 HttpOnly Cookie 下发
        assert refresh_cookie_name() in client.cookies
        assert csrf_cookie_name() in client.cookies
        return data

    async def test_refresh_token_valid(self, client: AsyncClient, test_user):
        # 1. Login to get refresh token
        login_data = await self.test_login_returns_refresh_token(client, test_user)
        old_access_token = login_data["access_token"]

        csrf = client.cookies.get(csrf_cookie_name())
        old_refresh = client.cookies.get(refresh_cookie_name())
        assert csrf
        assert old_refresh

        # Wait 1.1s
        await asyncio.sleep(1.1)

        # 2. Refresh
        response = await client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={csrf_header_name(): str(csrf)},
        )
        assert response.status_code == 200
        body = response.json()
        data = body["data"] if isinstance(body, dict) and "data" in body else body
        assert "access_token" in data

        # Refresh Token Rotation：refresh cookie 应该被轮换
        new_refresh = client.cookies.get(refresh_cookie_name())
        assert new_refresh
        assert str(new_refresh) != str(old_refresh)

        # New access token should be different (validity renewed)
        # Note: In strict equality check, if generated in same second it might be same content if no jti/randomness.
        # But create_access_token typically includes exp which differs by seconds.
        assert data["access_token"] != old_access_token

        # 3. Old refresh token should be invalid now
        current_csrf = client.cookies.get(csrf_cookie_name())
        assert current_csrf

        # httpx 不建议 per-request 传 cookies；这里用 client-level cookie 临时覆盖旧 refresh
        client.cookies.set(refresh_cookie_name(), str(old_refresh), path="/")
        client.cookies.set(csrf_cookie_name(), str(current_csrf), path="/")

        response2 = await client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={csrf_header_name(): str(current_csrf)},
        )
        assert response2.status_code == 401

        # 恢复回最新 refresh，避免影响后续测试
        client.cookies.set(refresh_cookie_name(), str(new_refresh), path="/")

    async def test_refresh_token_invalid(self, client: AsyncClient):
        # 缺少 refresh cookie -> 401
        response = await client.post(f"{settings.API_V1_STR}/auth/refresh")
        assert response.status_code == 401
