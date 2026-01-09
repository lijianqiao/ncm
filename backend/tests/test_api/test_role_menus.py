"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_role_menus.py
@DateTime: 2026-01-06 00:00:00
@Docs: 角色-菜单 绑定专门接口测试.
"""

from httpx import AsyncClient

from app.core.config import settings


class TestRoleMenusBinding:
    async def test_put_and_get_role_menus_success(self, client: AsyncClient, auth_headers: dict):
        # 1) 创建 2 个菜单
        m1 = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "RM Menu 1", "name": "RmMenu1", "path": "/rm-1", "sort": 1},
        )
        assert m1.status_code == 200
        menu_id_1 = m1.json()["data"]["id"]

        m2 = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "RM Menu 2", "name": "RmMenu2", "path": "/rm-2", "sort": 2},
        )
        assert m2.status_code == 200
        menu_id_2 = m2.json()["data"]["id"]

        # 2) 创建角色
        r = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "RM Role", "code": "rm_role", "sort": 1},
        )
        assert r.status_code == 200
        role_id = r.json()["data"]["id"]

        # 3) PUT 全量覆盖设置菜单（幂等）
        put_res = await client.put(
            f"{settings.API_V1_STR}/roles/{role_id}/menus",
            headers=auth_headers,
            json={"menu_ids": [menu_id_1, menu_id_2]},
        )
        assert put_res.status_code == 200
        data = put_res.json()["data"]
        assert isinstance(data, list)
        assert set(data) == {menu_id_1, menu_id_2}

        # 4) GET 回显
        get_res = await client.get(
            f"{settings.API_V1_STR}/roles/{role_id}/menus",
            headers=auth_headers,
        )
        assert get_res.status_code == 200
        data = get_res.json()["data"]
        assert isinstance(data, list)
        assert set(data) == {menu_id_1, menu_id_2}

        # 5) 再次 PUT 相同数据应幂等
        put_res_2 = await client.put(
            f"{settings.API_V1_STR}/roles/{role_id}/menus",
            headers=auth_headers,
            json={"menu_ids": [menu_id_1, menu_id_2]},
        )
        assert put_res_2.status_code == 200
        data = put_res_2.json()["data"]
        assert set(data) == {menu_id_1, menu_id_2}
