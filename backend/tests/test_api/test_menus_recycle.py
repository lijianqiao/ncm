import pytest
from httpx import AsyncClient

from app.core.config import settings


class TestMenuRecycle:
    @pytest.mark.asyncio
    async def test_recycle_bin(self, client: AsyncClient, auth_headers: dict[str, str], db_session):
        """
        测试菜单回收站功能 (创建 -> 删除 -> 回收站验证)。
        """
        # 0. Setup: Create a unique menu
        unique_name = "recycle_menu_001"
        data = {
            "title": "Recycle Menu AbC",
            "name": unique_name,
            "path": "/recycle-menu",
            "component": "Layout",
            "icon": "el-icon-delete",
            "sort": 1,
            "is_hidden": False,
        }
        # Create
        res = await client.post(f"{settings.API_V1_STR}/menus/", headers=auth_headers, json=data)
        assert res.status_code == 200
        menu_id = res.json()["data"]["id"]

        # 1. Delete the menu
        res = await client.delete(f"{settings.API_V1_STR}/menus/{menu_id}", headers=auth_headers)
        assert res.status_code == 200

        # 2. List recycle bin
        res = await client.get(f"{settings.API_V1_STR}/menus/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert "items" in data
        assert "total" in data

        # 2.1 keyword='' 等价于不传
        res_empty_kw = await client.get(
            f"{settings.API_V1_STR}/menus/recycle-bin",
            headers=auth_headers,
            params={"keyword": ""},
        )
        assert res_empty_kw.status_code == 200
        data_empty_kw = res_empty_kw.json()["data"]
        assert data_empty_kw["total"] == data["total"]
        assert {m["id"] for m in data_empty_kw["items"]} == {m["id"] for m in data["items"]}

        # 2.2 keyword 大小写不敏感（用 title 命中）
        res_ci = await client.get(
            f"{settings.API_V1_STR}/menus/recycle-bin",
            headers=auth_headers,
            params={"keyword": "recycle menu abc"},
        )
        assert res_ci.status_code == 200
        data_ci = res_ci.json()["data"]
        assert any(m["id"] == menu_id for m in data_ci["items"])

        # Ensure our deleted menu is in the list
        found = False
        for menu in data["items"]:
            if menu["name"] == unique_name:
                found = True
                assert menu["is_deleted"] is True
                assert menu["id"] == menu_id
                assert "created_at" in menu
                assert "updated_at" in menu
                break
        assert found

        # 3. Restore the menu
        res = await client.post(f"{settings.API_V1_STR}/menus/{menu_id}/restore", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["data"]["is_deleted"] is False

        # 4. Verify NOT in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/menus/recycle-bin", headers=auth_headers)
        items = res.json()["data"]["items"]
        assert not any(m["id"] == menu_id for m in items)

    @pytest.mark.asyncio
    async def test_batch_restore_menus(self, client: AsyncClient, auth_headers: dict[str, str], db_session):
        """测试菜单批量恢复功能 (创建2个 -> 批量删除 -> 批量恢复)."""

        # 0. Setup
        data_1 = {
            "title": "Recycle Menu Batch 001",
            "name": "recycle_menu_batch_001",
            "path": "/recycle-menu-batch-001",
            "component": "Layout",
            "icon": "el-icon-delete",
            "sort": 1,
            "is_hidden": False,
        }
        data_2 = {
            "title": "Recycle Menu Batch 002",
            "name": "recycle_menu_batch_002",
            "path": "/recycle-menu-batch-002",
            "component": "Layout",
            "icon": "el-icon-delete",
            "sort": 2,
            "is_hidden": False,
        }

        res = await client.post(f"{settings.API_V1_STR}/menus/", headers=auth_headers, json=data_1)
        assert res.status_code == 200
        menu_id_1 = res.json()["data"]["id"]

        res = await client.post(f"{settings.API_V1_STR}/menus/", headers=auth_headers, json=data_2)
        assert res.status_code == 200
        menu_id_2 = res.json()["data"]["id"]

        # 1. Batch delete
        res = await client.request(
            "DELETE",
            f"{settings.API_V1_STR}/menus/batch",
            headers=auth_headers,
            json={"ids": [menu_id_1, menu_id_2], "hard_delete": False},
        )
        assert res.status_code == 200

        # 2. Verify deleted in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/menus/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert any(m["id"] == menu_id_1 for m in items)
        assert any(m["id"] == menu_id_2 for m in items)

        # 3. Batch restore
        res = await client.post(
            f"{settings.API_V1_STR}/menus/batch/restore",
            headers=auth_headers,
            json={"ids": [menu_id_1, menu_id_2]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["success_count"] == 2
        assert res.json()["data"]["failed_ids"] == []

        # 4. Verify NOT in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/menus/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert not any(m["id"] == menu_id_1 for m in items)
        assert not any(m["id"] == menu_id_2 for m in items)
