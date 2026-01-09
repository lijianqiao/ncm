"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_users.py
@DateTime: 2025-12-30 16:50:00
@Docs: 用户 API 测试.
"""

from httpx import AsyncClient

from app.core.config import settings
from app.models.user import User


class TestUsersRead:
    """用户列表接口测试"""

    async def test_read_users_success(self, client: AsyncClient, auth_headers: dict):
        """测试获取用户列表"""
        response = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "total" in data["data"]
        assert "items" in data["data"]

    async def test_read_users_pagination(self, client: AsyncClient, auth_headers: dict):
        """测试分页参数"""
        response = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    async def test_read_users_filter_is_superuser(self, client: AsyncClient, auth_headers: dict):
        """测试 is_superuser 参数过滤生效（FastAPI 需要显式声明参数，否则会被忽略）。"""

        # 创建一个普通用户
        resp_normal = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "normal_user_1",
                "phone": "13500135010",
                "password": "Test@12345",
                "email": "normal1@example.com",
                "is_superuser": False,
            },
        )
        assert resp_normal.status_code == 200

        # 创建一个超级管理员用户
        resp_su = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "super_user_1",
                "phone": "13500135011",
                "password": "Test@12345",
                "email": "super1@example.com",
                "is_superuser": True,
            },
        )
        assert resp_su.status_code == 200

        # 过滤普通用户
        resp_list_normal = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_superuser": False},
        )
        assert resp_list_normal.status_code == 200
        items_normal = resp_list_normal.json()["data"]["items"]
        assert items_normal
        assert all(item["is_superuser"] is False for item in items_normal)

        # 过滤超级管理员
        resp_list_su = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_superuser": True},
        )
        assert resp_list_su.status_code == 200
        items_su = resp_list_su.json()["data"]["items"]
        assert items_su
        assert all(item["is_superuser"] is True for item in items_su)

    async def test_read_users_filter_is_active(self, client: AsyncClient, auth_headers: dict):
        """测试 is_active 参数过滤生效。"""

        # 创建一个启用用户
        resp_active = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "active_user_1",
                "phone": "13500135031",
                "password": "Test@12345",
                "email": "active1@example.com",
                "is_active": True,
                "is_superuser": False,
            },
        )
        assert resp_active.status_code == 200

        # 创建一个禁用用户
        resp_inactive = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "inactive_user_1",
                "phone": "13500135032",
                "password": "Test@12345",
                "email": "inactive1@example.com",
                "is_active": False,
                "is_superuser": False,
            },
        )
        assert resp_inactive.status_code == 200

        # 过滤启用
        resp_list_active = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": True},
        )
        assert resp_list_active.status_code == 200
        items_active = resp_list_active.json()["data"]["items"]
        assert items_active
        assert all(item["is_active"] is True for item in items_active)

        # 过滤禁用
        resp_list_inactive = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": False},
        )
        assert resp_list_inactive.status_code == 200
        items_inactive = resp_list_inactive.json()["data"]["items"]
        assert items_inactive
        assert all(item["is_active"] is False for item in items_inactive)

    async def test_read_users_keyword_mapping_status_and_superuser(self, client: AsyncClient, auth_headers: dict):
        """测试 keyword 对状态/超管的映射过滤（方案 A）。"""

        # 创建一个启用超管
        resp_su_active = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "kw_su_active",
                "phone": "13500135021",
                "password": "Test@12345",
                "email": "kw_su_active@example.com",
                "gender": "男",
                "is_superuser": True,
                "is_active": True,
            },
        )
        assert resp_su_active.status_code == 200

        # 创建一个禁用普通用户
        resp_normal_inactive = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "kw_normal_inactive",
                "phone": "13500135022",
                "password": "Test@12345",
                "email": "kw_normal_inactive@example.com",
                "gender": "女",
                "is_superuser": False,
                "is_active": False,
            },
        )
        assert resp_normal_inactive.status_code == 200

        # keyword=启用 -> is_active=True
        resp_active = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "启用"},
        )
        assert resp_active.status_code == 200
        items_active = resp_active.json()["data"]["items"]
        assert items_active
        assert all(item["is_active"] is True for item in items_active)

        # keyword=禁用 -> is_active=False
        resp_inactive = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "禁用"},
        )
        assert resp_inactive.status_code == 200
        items_inactive = resp_inactive.json()["data"]["items"]
        assert items_inactive
        assert all(item["is_active"] is False for item in items_inactive)

        # keyword=超管 -> is_superuser=True
        resp_su = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "超管"},
        )
        assert resp_su.status_code == 200
        items_su = resp_su.json()["data"]["items"]
        assert items_su
        assert all(item["is_superuser"] is True for item in items_su)

        # keyword=普通用户 -> is_superuser=False


class TestUsersCreate:
    async def test_create_user_with_dept_id_persists(self, client: AsyncClient, auth_headers: dict):
        """创建用户时传 dept_id，应正确写入并返回。"""

        # 1) 先创建部门
        resp_dept = await client.post(
            f"{settings.API_V1_STR}/depts/",
            headers=auth_headers,
            json={
                "name": "测试部门",
                "code": "TEST_DEPT",
                "parent_id": None,
                "sort": 0,
                "leader": "张三",
                "phone": None,
                "email": None,
            },
        )
        assert resp_dept.status_code == 200, resp_dept.text
        dept_id = resp_dept.json()["data"]["id"]

        # 2) 创建用户并选择部门
        resp_user = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": "dept_user_create_1",
                "phone": "13500135111",
                "password": "Test@12345",
                "email": "dept_user_create_1@example.com",
                "dept_id": dept_id,
                "is_superuser": False,
            },
        )
        assert resp_user.status_code == 200, resp_user.text
        data = resp_user.json()["data"]
        assert data["dept_id"] == dept_id

        # 3) 再查一次用户详情，确认持久化
        user_id = data["id"]
        resp_get = await client.get(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=auth_headers,
        )
        assert resp_get.status_code == 200, resp_get.text
        assert resp_get.json()["data"]["dept_id"] == dept_id
        resp_normal = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "普通用户"},
        )
        assert resp_normal.status_code == 200
        items_normal = resp_normal.json()["data"]["items"]
        assert items_normal
        assert all(item["is_superuser"] is False for item in items_normal)

    async def test_read_users_no_auth(self, client: AsyncClient):
        """测试无认证访问"""
        response = await client.get(f"{settings.API_V1_STR}/users/")

        assert response.status_code == 401


class TestUsersMe:
    """当前用户接口测试"""

    async def test_read_user_me(self, client: AsyncClient, auth_headers: dict):
        """测试获取当前用户信息"""
        response = await client.get(
            f"{settings.API_V1_STR}/users/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["username"] == "admin"

    async def test_update_user_me(self, client: AsyncClient, auth_headers: dict):
        """测试更新当前用户信息"""
        response = await client.put(
            f"{settings.API_V1_STR}/users/me",
            headers=auth_headers,
            json={"nickname": "管理员昵称"},
        )

        assert response.status_code == 200

    async def test_update_user_me_forbid_username(self, client: AsyncClient, auth_headers: dict):
        """测试禁止修改 username"""
        response = await client.put(
            f"{settings.API_V1_STR}/users/me",
            headers=auth_headers,
            json={"username": "hacked"},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == 422
        # message 由全局 validation handler 统一返回
        assert any("用户名不允许修改" in d.get("message", "") for d in body.get("details", []))


class TestUsersPassword:
    """密码接口测试"""

    async def test_change_password_me(self, client: AsyncClient, auth_headers: dict, test_superuser: User):
        """测试修改自己密码"""
        response = await client.put(
            f"{settings.API_V1_STR}/users/me/password",
            headers=auth_headers,
            json={
                "old_password": "Admin@123456",
                "new_password": "Admin@789012",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "密码修改成功"

    async def test_change_password_wrong_old(self, client: AsyncClient, auth_headers: dict):
        """测试旧密码错误"""
        response = await client.put(
            f"{settings.API_V1_STR}/users/me/password",
            headers=auth_headers,
            json={
                "old_password": "wrongpassword",
                "new_password": "New@123456",
            },
        )

        assert response.status_code == 400


class TestUsersBatchDelete:
    """批量删除接口测试"""

    async def test_batch_delete_empty_list(self, client: AsyncClient, auth_headers: dict):
        """测试空列表删除"""
        response = await client.request(
            "DELETE",
            f"{settings.API_V1_STR}/users/batch",
            headers=auth_headers,
            json={"ids": [], "hard_delete": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["success_count"] == 0
