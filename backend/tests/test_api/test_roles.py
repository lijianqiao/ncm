"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_roles.py
@DateTime: 2025-12-30 21:20:00
@Docs: Role API 接口测试.
"""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rbac import Role


class TestRolesRead:
    """角色查询接口测试"""

    async def test_read_roles_success(self, client: AsyncClient, auth_headers: dict):
        """测试获取角色列表"""
        response = await client.get(f"{settings.API_V1_STR}/roles/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]
        # 至少默认有初始化的角色（如果 initial_data 未运行则可能为空，但测试环境通常是空的）
        # 我们可以先创建一个
        # 但我们应该尽量让测试独立。这里只检查结构。

    async def test_read_roles_keyword_mapping_status(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试 keyword 对角色状态的映射过滤（方案 A）。"""

        # 通过 API 创建 2 个角色（默认 is_active=True）
        resp_a = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "KW Role Active", "code": "kw_role_active", "sort": 1},
        )
        assert resp_a.status_code == 200
        role_active_id = UUID(resp_a.json()["data"]["id"])

        resp_b = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "KW Role Inactive", "code": "kw_role_inactive", "sort": 2},
        )
        assert resp_b.status_code == 200
        role_inactive_id = UUID(resp_b.json()["data"]["id"])

        # 直接在 DB 中把其中一个改为禁用（当前 API 未暴露 is_active 更新字段）
        await db_session.execute(update(Role).where(Role.id == role_inactive_id).values(is_active=False))
        await db_session.commit()

        # keyword=启用 -> is_active=True
        resp_active = await client.get(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "启用"},
        )
        assert resp_active.status_code == 200
        items_active = resp_active.json()["data"]["items"]
        assert items_active
        assert all(item["is_active"] is True for item in items_active)
        assert any(item["id"] == str(role_active_id) for item in items_active)

        # keyword=禁用 -> is_active=False
        resp_inactive = await client.get(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "禁用"},
        )
        assert resp_inactive.status_code == 200
        items_inactive = resp_inactive.json()["data"]["items"]
        assert items_inactive
        assert all(item["is_active"] is False for item in items_inactive)
        assert any(item["id"] == str(role_inactive_id) for item in items_inactive)

    async def test_read_roles_filter_is_active(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """测试 is_active 参数过滤生效。"""

        resp_a = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "Active Filter Role", "code": "active_filter_role", "sort": 1},
        )
        assert resp_a.status_code == 200
        role_active_id = UUID(resp_a.json()["data"]["id"])

        resp_b = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "Inactive Filter Role", "code": "inactive_filter_role", "sort": 2},
        )
        assert resp_b.status_code == 200
        role_inactive_id = UUID(resp_b.json()["data"]["id"])

        await db_session.execute(update(Role).where(Role.id == role_inactive_id).values(is_active=False))
        await db_session.commit()

        resp_list_active = await client.get(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": True},
        )
        assert resp_list_active.status_code == 200
        items_active = resp_list_active.json()["data"]["items"]
        assert items_active
        assert all(item["is_active"] is True for item in items_active)
        assert any(item["id"] == str(role_active_id) for item in items_active)

        resp_list_inactive = await client.get(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": False},
        )
        assert resp_list_inactive.status_code == 200
        items_inactive = resp_list_inactive.json()["data"]["items"]
        assert items_inactive
        assert all(item["is_active"] is False for item in items_inactive)
        assert any(item["id"] == str(role_inactive_id) for item in items_inactive)


class TestRolesCreate:
    """角色创建接口测试"""

    async def test_create_role_success(self, client: AsyncClient, auth_headers: dict):
        """测试创建角色"""
        response = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "API Role", "code": "api_role", "sort": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["code"] == "api_role"

    async def test_create_role_duplicate(self, client: AsyncClient, auth_headers: dict):
        """测试创建重复角色"""
        # 先创建一个
        await client.post(
            f"{settings.API_V1_STR}/roles/", headers=auth_headers, json={"name": "Dup Role", "code": "dup_role"}
        )

        # 再创建同一个 code
        response = await client.post(
            f"{settings.API_V1_STR}/roles/", headers=auth_headers, json={"name": "Dup Role 2", "code": "dup_role"}
        )
        # Service 抛出 BadRequestException，通常映射为 400
        assert response.status_code == 400


class TestRolesUpdate:
    """角色更新接口测试"""

    async def test_update_role(self, client: AsyncClient, auth_headers: dict):
        # Setup
        res = await client.post(
            f"{settings.API_V1_STR}/roles/", headers=auth_headers, json={"name": "To Update", "code": "update_api_role"}
        )
        role_id = res.json()["data"]["id"]

        # Update
        response = await client.put(
            f"{settings.API_V1_STR}/roles/{role_id}", headers=auth_headers, json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Name"


class TestRolesDelete:
    """角色删除接口测试"""

    async def test_delete_role(self, client: AsyncClient, auth_headers: dict):
        # Setup
        res = await client.post(
            f"{settings.API_V1_STR}/roles/", headers=auth_headers, json={"name": "To Delete", "code": "delete_api_role"}
        )
        role_id = res.json()["data"]["id"]

        # Delete
        response = await client.delete(f"{settings.API_V1_STR}/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify
        await client.get(f"{settings.API_V1_STR}/roles/{role_id}", headers=auth_headers)
        assert response.json()["data"]["is_deleted"] is True

    async def test_batch_delete_roles(self, client: AsyncClient, auth_headers: dict):
        # Setup 2 roles
        ids = []
        for i in range(2):
            res = await client.post(
                f"{settings.API_V1_STR}/roles/", headers=auth_headers, json={"name": f"Batch {i}", "code": f"batch_{i}"}
            )
            ids.append(res.json()["data"]["id"])

        response = await client.request(
            "DELETE", f"{settings.API_V1_STR}/roles/batch", headers=auth_headers, json={"ids": ids}
        )
        assert response.status_code == 200
        assert response.json()["data"]["success_count"] == 2
