import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.enums import MenuType
from app.models.rbac import Menu, Role
from app.models.user import User


class TestUsersPermissionControl:
    @pytest.mark.asyncio
    async def test_user_with_user_list_permission_can_read_users(
        self,
        client: AsyncClient,
        db_session,
        test_user: User,
    ):
        """测试非超管用户具备 user:list 权限后可访问用户列表。"""

        menu = Menu(
            title="用户-列表",
            name="PermUserList",
            parent_id=None,
            path=None,
            component=None,
            icon=None,
            sort=1,
            type=MenuType.PERMISSION,
            is_hidden=True,
            permission="user:list",
            is_active=True,
            is_deleted=False,
        )
        role = Role(
            name="用户管理员",
            code="user_manager",
            description="仅用于测试 user:list 权限",
            sort=1,
            is_active=True,
            is_deleted=False,
        )
        role.menus = [menu]
        test_user.roles = [role]

        db_session.add_all([menu, role, test_user])
        await db_session.commit()

        login_res = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "testuser", "password": "Test@123456"},
        )
        token = login_res.json()["access_token"]
        normal_auth_headers = {"Authorization": f"Bearer {token}"}

        res = await client.get(
            f"{settings.API_V1_STR}/users/",
            headers=normal_auth_headers,
        )
        assert res.status_code == 200
