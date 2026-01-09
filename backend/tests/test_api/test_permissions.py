"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_permissions.py
@DateTime: 2026-01-06 00:00:00
@Docs: 权限字典接口测试。
"""

from httpx import AsyncClient

from app.core.config import settings
from app.core.permissions import PermissionCode


class TestPermissions:
    async def test_list_permissions_success(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{settings.API_V1_STR}/permissions/", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        items = body["data"]
        assert isinstance(items, list)

        codes = {it["code"] for it in items}
        assert PermissionCode.MENU_LIST.value in codes
        assert PermissionCode.ROLE_LIST.value in codes
        assert PermissionCode.LOG_LOGIN_LIST.value in codes
