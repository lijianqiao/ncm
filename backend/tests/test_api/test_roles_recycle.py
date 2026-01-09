import pytest
from httpx import AsyncClient

from app.core.config import settings


class TestRoleRecycle:
    @pytest.mark.asyncio
    async def test_recycle_bin(self, client: AsyncClient, auth_headers: dict[str, str], db_session):
        """
        测试角色回收站功能 (创建 -> 删除 -> 回收站验证)。
        """
        # 0. Setup: Create a unique role
        unique_code = "Recycle_Role_AbC"
        data = {"name": "Recycle Role", "code": unique_code, "description": "For ReCyClE Bin Test", "sort": 1}
        # Create
        res = await client.post(f"{settings.API_V1_STR}/roles/", headers=auth_headers, json=data)
        assert res.status_code == 200
        role_id = res.json()["data"]["id"]

        # 1. Delete the role
        res = await client.delete(f"{settings.API_V1_STR}/roles/{role_id}", headers=auth_headers)
        assert res.status_code == 200

        # 2. List recycle bin
        res = await client.get(f"{settings.API_V1_STR}/roles/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert "items" in data
        assert "total" in data

        # 2.1 keyword='' 等价于不传
        res_empty_kw = await client.get(
            f"{settings.API_V1_STR}/roles/recycle-bin",
            headers=auth_headers,
            params={"keyword": ""},
        )
        assert res_empty_kw.status_code == 200
        data_empty_kw = res_empty_kw.json()["data"]
        assert data_empty_kw["total"] == data["total"]
        assert {r["id"] for r in data_empty_kw["items"]} == {r["id"] for r in data["items"]}

        # 2.2 keyword 大小写不敏感（用 code 命中）
        res_ci = await client.get(
            f"{settings.API_V1_STR}/roles/recycle-bin",
            headers=auth_headers,
            params={"keyword": "recycle_role_abc"},
        )
        assert res_ci.status_code == 200
        data_ci = res_ci.json()["data"]
        assert any(r["id"] == role_id for r in data_ci["items"])

        # Ensure our deleted role is in the list with correct fields
        found = False
        for role in data["items"]:
            if role["code"] == unique_code:
                found = True
                assert role["is_deleted"] is True
                assert role["id"] == role_id
                assert "created_at" in role
                assert "updated_at" in role
                break
        assert found

        # 3. Restore the role
        res = await client.post(f"{settings.API_V1_STR}/roles/{role_id}/restore", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["data"]["is_deleted"] is False

        # 4. Verify NOT in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/roles/recycle-bin", headers=auth_headers)
        items = res.json()["data"]["items"]
        assert not any(r["id"] == role_id for r in items)

    @pytest.mark.asyncio
    async def test_batch_restore_roles(self, client: AsyncClient, auth_headers: dict[str, str], db_session):
        """测试角色批量恢复功能 (创建2个 -> 批量删除 -> 批量恢复)."""

        # 0. Setup
        data_1 = {
            "name": "Recycle Role Batch 001",
            "code": "Recycle_Role_Batch_001",
            "description": "For batch recycle bin test 001",
            "sort": 1,
        }
        data_2 = {
            "name": "Recycle Role Batch 002",
            "code": "Recycle_Role_Batch_002",
            "description": "For batch recycle bin test 002",
            "sort": 2,
        }

        res = await client.post(f"{settings.API_V1_STR}/roles/", headers=auth_headers, json=data_1)
        assert res.status_code == 200
        role_id_1 = res.json()["data"]["id"]

        res = await client.post(f"{settings.API_V1_STR}/roles/", headers=auth_headers, json=data_2)
        assert res.status_code == 200
        role_id_2 = res.json()["data"]["id"]

        # 1. Batch delete
        res = await client.request(
            "DELETE",
            f"{settings.API_V1_STR}/roles/batch",
            headers=auth_headers,
            json={"ids": [role_id_1, role_id_2], "hard_delete": False},
        )
        assert res.status_code == 200

        # 2. Verify deleted in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/roles/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert any(r["id"] == role_id_1 for r in items)
        assert any(r["id"] == role_id_2 for r in items)

        # 3. Batch restore
        res = await client.post(
            f"{settings.API_V1_STR}/roles/batch/restore",
            headers=auth_headers,
            json={"ids": [role_id_1, role_id_2]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["success_count"] == 2
        assert res.json()["data"]["failed_ids"] == []

        # 4. Verify NOT in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/roles/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert not any(r["id"] == role_id_1 for r in items)
        assert not any(r["id"] == role_id_2 for r in items)
