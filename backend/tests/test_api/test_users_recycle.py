import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.user import User


class TestUserSoftDelete:
    @pytest.mark.asyncio
    async def test_create_user_conflict_soft_deleted(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session
    ):
        """
        测试创建用户时，用户名已存在但被软删除的情况。
        应该返回 400 且提示联系管理员恢复。
        """
        # 1. Create a user
        unique_username = "deleted_user"
        data = {
            "username": unique_username,
            "password": "Password@123",
            "email": "deleted@example.com",
            "phone": "+8613900000001",
            "nickname": "To Be Deleted",
        }
        res = await client.post(f"{settings.API_V1_STR}/users/", headers=auth_headers, json=data)
        assert res.status_code == 200, res.text
        user_id = res.json()["data"]["id"]

        # 2. Delete the user
        batch_data = {"ids": [user_id], "hard_delete": False}
        res = await client.request(
            "DELETE", f"{settings.API_V1_STR}/users/batch", headers=auth_headers, json=batch_data
        )
        assert res.status_code == 200

        # 3. Try to create the same user again
        res = await client.post(f"{settings.API_V1_STR}/users/", headers=auth_headers, json=data)
        assert res.status_code == 400
        assert "该用户名已被注销/删除" in res.json()["message"]

    @pytest.mark.asyncio
    async def test_recycle_bin(self, client: AsyncClient, auth_headers: dict[str, str], db_session):
        """
        测试回收站功能。
        """
        # 0. Setup: Create and delete a user
        unique_username = "recycle_user"
        data = {
            "username": unique_username,
            "password": "Password@123",
            "email": "recycle@example.com",
            "phone": "+8613900000002",
            "nickname": "ReCyClE NiCk",
        }
        # Create
        res = await client.post(f"{settings.API_V1_STR}/users/", headers=auth_headers, json=data)
        assert res.status_code == 200
        user_id = res.json()["data"]["id"]
        # Delete
        batch_data = {"ids": [user_id], "hard_delete": False}
        await client.request("DELETE", f"{settings.API_V1_STR}/users/batch", headers=auth_headers, json=batch_data)

        # 1. List recycle bin
        res = await client.get(f"{settings.API_V1_STR}/users/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert "items" in data
        assert "total" in data

        # 1.1 keyword='' 等价于不传
        res_empty_kw = await client.get(
            f"{settings.API_V1_STR}/users/recycle-bin",
            headers=auth_headers,
            params={"keyword": ""},
        )
        assert res_empty_kw.status_code == 200
        data_empty_kw = res_empty_kw.json()["data"]
        assert data_empty_kw["total"] == data["total"]
        assert {u["id"] for u in data_empty_kw["items"]} == {u["id"] for u in data["items"]}

        # 1.2 keyword 大小写不敏感（用 nickname 命中）
        res_ci = await client.get(
            f"{settings.API_V1_STR}/users/recycle-bin",
            headers=auth_headers,
            params={"keyword": "recycle nick"},
        )
        assert res_ci.status_code == 200
        data_ci = res_ci.json()["data"]
        assert any(u["username"] == unique_username for u in data_ci["items"])

        # Ensure our deleted user is in the list
        found = False
        for user in data["items"]:
            if user["username"] == unique_username:
                found = True
                assert user["is_deleted"] is True
                assert "created_at" in user
                assert "updated_at" in user
                break
        assert found

    @pytest.mark.asyncio
    async def test_recycle_bin_forbidden(
        self,
        client: AsyncClient,
        test_user: User,  # Normal user
    ):
        """
        测试普通用户无权访问回收站。
        """
        # Login as normal user
        login_data = {"username": "testuser", "password": "Test@123456"}
        login_res = await client.post(f"{settings.API_V1_STR}/auth/login", data=login_data)
        token = login_res.json()["access_token"]
        normal_auth_headers = {"Authorization": f"Bearer {token}"}

        res = await client.get(f"{settings.API_V1_STR}/users/recycle-bin", headers=normal_auth_headers)
        assert res.status_code == 403
