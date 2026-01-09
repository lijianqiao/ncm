"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_menus.py
@DateTime: 2025-12-30 21:40:00
@Docs: Menu API 接口测试.
"""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import MenuType
from app.core.permissions import PermissionCode
from app.crud.crud_menu import menu as menu_crud
from app.crud.crud_role import role as role_crud
from app.models.rbac import Menu, UserRole
from app.schemas.menu import MenuCreate
from app.schemas.role import RoleCreate


class TestMenusRead:
    async def test_read_menus_success(self, client: AsyncClient, auth_headers: dict):
        response = await client.get(f"{settings.API_V1_STR}/menus/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    async def test_read_menus_keyword_mapping_hidden(self, client: AsyncClient, auth_headers: dict):
        """测试 keyword 对菜单隐藏状态的映射过滤（方案 A）。"""

        # 创建一个隐藏菜单
        resp_hidden = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "KW Hidden Menu",
                "name": "KwHiddenMenu",
                "path": "/kw-hidden",
                "sort": 10,
                "is_hidden": True,
                "permission": PermissionCode.MENU_LIST.value,
            },
        )
        assert resp_hidden.status_code == 200

        # 创建一个显示菜单
        resp_visible = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "KW Visible Menu",
                "name": "KwVisibleMenu",
                "path": "/kw-visible",
                "sort": 11,
                "is_hidden": False,
                "permission": PermissionCode.MENU_LIST.value,
            },
        )
        assert resp_visible.status_code == 200

        # keyword=隐藏 -> is_hidden=True
        resp_list_hidden = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "隐藏"},
        )
        assert resp_list_hidden.status_code == 200
        items_hidden = resp_list_hidden.json()["data"]["items"]
        assert items_hidden
        assert all(item["is_hidden"] is True for item in items_hidden)

        # keyword=显示 -> is_hidden=False
        resp_list_visible = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "显示"},
        )
        assert resp_list_visible.status_code == 200
        items_visible = resp_list_visible.json()["data"]["items"]
        assert items_visible
        assert all(item["is_hidden"] is False for item in items_visible)

    async def test_read_menus_filter_is_active(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        """测试 is_active 参数过滤生效。"""

        resp_a = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "Active Menu", "name": "ActiveMenu", "path": "/active-menu", "sort": 20},
        )
        assert resp_a.status_code == 200
        menu_active_id = UUID(resp_a.json()["data"]["id"])

        resp_b = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "Inactive Menu", "name": "InactiveMenu", "path": "/inactive-menu", "sort": 21},
        )
        assert resp_b.status_code == 200
        menu_inactive_id = UUID(resp_b.json()["data"]["id"])

        await db_session.execute(update(Menu).where(Menu.id == menu_inactive_id).values(is_active=False))
        await db_session.commit()

        resp_list_active = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": True},
        )
        assert resp_list_active.status_code == 200
        items_active = resp_list_active.json()["data"]["items"]
        assert items_active
        active_ids = {item["id"] for item in items_active}
        assert str(menu_active_id) in active_ids
        assert str(menu_inactive_id) not in active_ids

        resp_list_inactive = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_active": False},
        )
        assert resp_list_inactive.status_code == 200
        items_inactive = resp_list_inactive.json()["data"]["items"]
        assert items_inactive
        inactive_ids = {item["id"] for item in items_inactive}
        assert str(menu_inactive_id) in inactive_ids
        assert str(menu_active_id) not in inactive_ids

    async def test_read_menus_filter_is_hidden(self, client: AsyncClient, auth_headers: dict):
        """测试 is_hidden 参数过滤生效。"""

        resp_hidden = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "Hidden Menu",
                "name": "HiddenMenu",
                "path": "/hidden-menu",
                "sort": 30,
                "is_hidden": True,
                "permission": PermissionCode.MENU_LIST.value,
            },
        )
        assert resp_hidden.status_code == 200
        hidden_id = resp_hidden.json()["data"]["id"]

        resp_visible = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "Visible Menu",
                "name": "VisibleMenu",
                "path": "/visible-menu",
                "sort": 31,
                "is_hidden": False,
                "permission": PermissionCode.MENU_LIST.value,
            },
        )
        assert resp_visible.status_code == 200
        visible_id = resp_visible.json()["data"]["id"]

        resp_list_hidden = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_hidden": True},
        )
        assert resp_list_hidden.status_code == 200
        items_hidden = resp_list_hidden.json()["data"]["items"]
        assert items_hidden
        assert all(item["is_hidden"] is True for item in items_hidden)
        hidden_ids = {item["id"] for item in items_hidden}
        assert hidden_id in hidden_ids
        assert visible_id not in hidden_ids

        resp_list_visible = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "is_hidden": False},
        )
        assert resp_list_visible.status_code == 200
        items_visible = resp_list_visible.json()["data"]["items"]
        assert items_visible
        assert all(item["is_hidden"] is False for item in items_visible)
        visible_ids = {item["id"] for item in items_visible}
        assert visible_id in visible_ids
        assert hidden_id not in visible_ids

    async def test_create_menu_with_type(self, client: AsyncClient, auth_headers: dict):
        """测试菜单 type 字段可写入且能在响应中返回。"""

        resp = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "Catalog Menu",
                "name": "CatalogMenu",
                "sort": 40,
                "type": MenuType.CATALOG.value,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["type"] == MenuType.CATALOG.value

        menu_id = body["data"]["id"]
        resp_list = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50},
        )
        assert resp_list.status_code == 200
        items = resp_list.json()["data"]["items"]
        found = [it for it in items if it["id"] == menu_id]
        assert found
        assert found[0]["type"] == MenuType.CATALOG.value

        resp_list_catalog = await client.get(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "type": MenuType.CATALOG.value},
        )
        assert resp_list_catalog.status_code == 200
        items_catalog = resp_list_catalog.json()["data"]["items"]
        assert items_catalog
        assert all(it["type"] == MenuType.CATALOG.value for it in items_catalog)
        catalog_ids = {it["id"] for it in items_catalog}
        assert menu_id in catalog_ids


class TestMenusMe:
    async def test_get_my_menus_superuser(self, client: AsyncClient, auth_headers: dict):
        res = await client.get(f"{settings.API_V1_STR}/menus/me", headers=auth_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert isinstance(body["data"], list)

    async def test_get_my_menus_normal_user_no_roles(self, client: AsyncClient, test_user):
        login_res = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "testuser", "password": "Test@123456"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get(f"{settings.API_V1_STR}/menus/me", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert isinstance(body["data"], list)

    async def test_read_menus_success_with_children(self, client: AsyncClient, auth_headers: dict):
        # 创建父菜单
        parent_res = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "Parent Menu", "name": "ParentMenu", "path": "/parent", "sort": 1},
        )
        assert parent_res.status_code == 200
        parent_id = parent_res.json()["data"]["id"]

        # 创建子菜单
        child_res = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={
                "title": "Child Menu",
                "name": "ChildMenu",
                "parent_id": parent_id,
                "path": "/parent/child",
                "sort": 2,
            },
        )
        assert child_res.status_code == 200

        # 读取列表：不应因 children 懒加载触发 MissingGreenlet
        response = await client.get(f"{settings.API_V1_STR}/menus/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]


class TestMenusOptions:
    async def test_get_menu_options_requires_permission_for_normal_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user,
    ):
        # 构造三层菜单树，确保序列化不会触发 children 懒加载
        root = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="RootOpt",
                name="RootOpt",
                parent_id=None,
                path="/root-opt",
                component=None,
                icon=None,
                sort=1,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )
        child = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="ChildOpt",
                name="ChildOpt",
                parent_id=root.id,
                path="/root-opt/child",
                component=None,
                icon=None,
                sort=2,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )
        await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="GrandChildOpt",
                name="GrandChildOpt",
                parent_id=child.id,
                path="/root-opt/child/grand",
                component=None,
                icon=None,
                sort=3,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )

        # 1) 创建权限点菜单（menu:options:list）
        perm_menu = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="菜单-可分配选项",
                name="PermMenuOptionsListTest",
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=True,
                permission="menu:options:list",
            ),  # pyright: ignore[reportCallIssue]
        )

        # 2) 创建角色并绑定该权限菜单
        role = await role_crud.create(
            db_session,
            obj_in=RoleCreate(name="OptionsRole", code="options_role", description=None, sort=0),
        )
        await role_crud.update(db_session, db_obj=role, obj_in={"menu_ids": [perm_menu.id]})

        # 3) 绑定用户-角色
        db_session.add(UserRole(user_id=test_user.id, role_id=role.id))
        await db_session.commit()

        # 4) 用普通用户登录
        login_res = await client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={"username": "testuser", "password": "Test@123456"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 5) 访问 options
        res = await client.get(f"{settings.API_V1_STR}/menus/options", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert isinstance(body["data"], list)


class TestMenusCreate:
    async def test_create_menu_success(self, client: AsyncClient, auth_headers: dict):
        response = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "API Menu", "name": "ApiMenu", "path": "/api-menu", "sort": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "API Menu"


class TestMenusUpdate:
    async def test_update_menu(self, client: AsyncClient, auth_headers: dict):
        # Create
        res = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "To Update", "name": "ToUpdateApi", "path": "/to-update-api"},
        )
        menu_id = res.json()["data"]["id"]

        # Update
        response = await client.put(
            f"{settings.API_V1_STR}/menus/{menu_id}", headers=auth_headers, json={"title": "Updated Title"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "Updated Title"


class TestMenusDelete:
    async def test_delete_menu(self, client: AsyncClient, auth_headers: dict):
        # Create
        res = await client.post(
            f"{settings.API_V1_STR}/menus/",
            headers=auth_headers,
            json={"title": "To Delete", "name": "ToDelApi", "path": "/to-del-api"},
        )
        menu_id = res.json()["data"]["id"]

        # Delete
        response = await client.delete(f"{settings.API_V1_STR}/menus/{menu_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["data"]["is_deleted"] is True

    async def test_batch_delete_menus(self, client: AsyncClient, auth_headers: dict):
        # Create 2 menus
        ids = []
        for i in range(2):
            res = await client.post(
                f"{settings.API_V1_STR}/menus/",
                headers=auth_headers,
                json={"title": f"Batch {i}", "name": f"Batch{i}", "path": f"/batch-{i}"},
            )
            ids.append(res.json()["data"]["id"])

        # Batch delete
        response = await client.request(
            "DELETE", f"{settings.API_V1_STR}/menus/batch", headers=auth_headers, json={"ids": ids}
        )
        assert response.status_code == 200
        assert response.json()["data"]["success_count"] == 2
