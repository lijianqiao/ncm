import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.user import User


class TestUserAdminUpdate:
    @pytest.mark.asyncio
    async def test_admin_update_user_basic(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],  # Superuser headers
        test_user: User,
    ):
        """
        测试超级管理员修改用户信息 (基本信息)。
        """
        data = {"nickname": "Updated Nickname", "phone": "+8613900139000", "is_active": False}
        res = await client.put(
            f"{settings.API_V1_STR}/users/{test_user.id}",
            headers=auth_headers,
            json=data,
        )
        assert res.status_code == 200
        content = res.json()["data"]
        assert content["nickname"] == "Updated Nickname"
        assert content["phone"] == "+8613900139000"
        assert content["is_active"] is False

    @pytest.mark.asyncio
    async def test_admin_update_user_forbidden_for_user(
        self,
        client: AsyncClient,
        test_user: User,
        test_superuser: User,  # Another target
    ):
        """
        测试普通用户无权修改其他用户信息。
        """
        # Login as normal user
        login_data = {"username": "testuser", "password": "Test@123456"}
        login_res = await client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
        token = login_res.json()["access_token"]
        normal_auth_headers = {"Authorization": f"Bearer {token}"}

        data = {"nickname": "Hacker"}
        res = await client.put(
            f"{settings.API_V1_STR}/users/{test_superuser.id}",
            headers=normal_auth_headers,
            json=data,
        )
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_update_user_conflict(
        self, client: AsyncClient, auth_headers: dict[str, str], test_user: User, db_session
    ):
        """
        测试修改手机号/邮箱冲突。
        需先创建另一个用户来制造冲突。
        """
        from app.core.security import get_password_hash

        # Create a second user
        user2 = User(
            username="conflict_user",
            password=get_password_hash("Test@123456"),
            phone="+8613800138999",
            email="conflict@example.com",
            nickname="Conflict",
            is_active=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        # Try to update test_user's phone to user2's phone
        data = {"phone": "+8613800138999"}
        res = await client.put(
            f"{settings.API_V1_STR}/users/{test_user.id}",
            headers=auth_headers,
            json=data,
        )
        assert res.status_code == 400
        assert "手机号已存在" in res.json()["message"]
