"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_auth.py
@DateTime: 2025-12-30 16:50:00
@Docs: 认证 API 测试.
"""

from httpx import AsyncClient

from app.core.config import settings
from app.models.user import User


class TestAuthLogin:
    """登录接口测试"""

    async def test_login_success(self, client: AsyncClient, test_superuser: User):
        """测试登录成功"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "admin", "password": "Admin@123456"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_superuser: User):
        """测试登录密码错误"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )

        assert response.status_code == 400

    async def test_login_user_not_found(self, client: AsyncClient):
        """测试登录用户不存在"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "nonexistent", "password": "Test@12345"},
        )

        assert response.status_code == 400


class TestAuthTestToken:
    """Token 测试接口"""

    async def test_test_token_success(self, client: AsyncClient, auth_headers: dict):
        """测试 Token 有效"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/test-token",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["username"] == "admin"

    async def test_test_token_no_auth(self, client: AsyncClient):
        """测试无 Token"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/test-token",
        )

        assert response.status_code == 401

    async def test_test_token_invalid(self, client: AsyncClient):
        """测试无效 Token"""
        response = await client.post(
            f"{settings.API_V1_STR}/auth/test-token",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
