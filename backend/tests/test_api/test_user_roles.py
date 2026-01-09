"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_user_roles.py
@DateTime: 2026-01-06 00:00:00
@Docs: 用户-角色 绑定专门接口测试.
"""

import uuid

from httpx import AsyncClient

from app.core.config import settings


class TestUserRolesBinding:
    async def test_put_and_get_user_roles_success(self, client: AsyncClient, auth_headers: dict):
        uniq = uuid.uuid4().hex[:8]

        # 1) 创建 2 个角色
        r1 = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "UR Role 1", "code": f"ur_role_1_{uniq}", "sort": 1},
        )
        role_id_1 = r1.json()["data"]["id"]

        r2 = await client.post(
            f"{settings.API_V1_STR}/roles/",
            headers=auth_headers,
            json={"name": "UR Role 2", "code": f"ur_role_2_{uniq}", "sort": 2},
        )
        assert r2.status_code == 200
        role_id_2 = r2.json()["data"]["id"]

        # 2) 创建一个用户
        u1 = await client.post(
            f"{settings.API_V1_STR}/users/",
            headers=auth_headers,
            json={
                "username": f"ur_test_user_{uniq}",
                "password": "Test@123456",
                "phone": f"1380013{int(uniq[:4], 16) % 10000:04d}",
                "nickname": "User Roles Test",
                "gender": "male",
            },
        )
        assert u1.status_code == 200
        user_id = u1.json()["data"]["id"]

        # 3) 全量覆盖设置用户角色
        put_res = await client.put(
            f"{settings.API_V1_STR}/users/{user_id}/roles",
            headers=auth_headers,
            json={"role_ids": [role_id_1, role_id_2]},
        )
        assert put_res.status_code == 200
        data = put_res.json()["data"]
        assert isinstance(data, list)
        assert {item["id"] for item in data} == {role_id_1, role_id_2}

        # 4) GET 回显
        get_res = await client.get(
            f"{settings.API_V1_STR}/users/{user_id}/roles",
            headers=auth_headers,
        )
        assert get_res.status_code == 200
        data = get_res.json()["data"]
        assert isinstance(data, list)
        assert {item["id"] for item in data} == {role_id_1, role_id_2}

        # 5) 幂等：重复 PUT 相同集合
        put_res_2 = await client.put(
            f"{settings.API_V1_STR}/users/{user_id}/roles",
            headers=auth_headers,
            json={"role_ids": [role_id_1, role_id_2]},
        )
        assert put_res_2.status_code == 200
        data = put_res_2.json()["data"]
        assert {item["id"] for item in data} == {role_id_1, role_id_2}
