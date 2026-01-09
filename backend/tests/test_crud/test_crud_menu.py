"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_crud_menu.py
@DateTime: 2025-12-30 21:30:00
@Docs: Menu CRUD 测试.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_menu import menu as menu_crud
from app.schemas.menu import MenuCreate, MenuUpdate


class TestCRUDMenuCreate:
    """菜单创建测试"""

    async def test_create_menu(self, db_session: AsyncSession):
        """测试创建菜单"""
        menu_in = MenuCreate(
            title="Test Menu",
            name="TestMenu",
            path="/test",
            component="Layout",
            parent_id=None,
            icon=None,
            sort=0,
            is_hidden=False,
            permission=None,
        )  # pyright: ignore[reportCallIssue]
        menu = await menu_crud.create(db_session, obj_in=menu_in)

        assert menu.title == "Test Menu"
        assert menu.name == "TestMenu"
        assert menu.id is not None

    async def test_create_sub_menu(self, db_session: AsyncSession):
        """测试创建子菜单"""
        # 父菜单
        parent = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="Parent",
                name="Parent",
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )

        # 子菜单
        child_in = MenuCreate(
            title="Child",
            name="Child",
            parent_id=parent.id,
            path=None,
            component=None,
            icon=None,
            sort=0,
            is_hidden=False,
            permission=None,
        )  # pyright: ignore[reportCallIssue]
        child = await menu_crud.create(db_session, obj_in=child_in)

        assert child.parent_id == parent.id


class TestCRUDMenuGet:
    """菜单查询测试"""

    async def test_get_menu(self, db_session: AsyncSession):
        """测试获取单个菜单"""
        menu = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="Get Menu",
                name="GetMenu",
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )
        stored_menu = await menu_crud.get(db_session, id=menu.id)
        assert stored_menu is not None
        assert stored_menu.title == "Get Menu"

    async def test_get_multi(self, db_session: AsyncSession):
        """测试获取列表"""
        for i in range(3):
            await menu_crud.create(
                db_session,
                obj_in=MenuCreate(
                    title=f"Menu {i}",
                    name=f"Menu{i}",
                    parent_id=None,
                    path=None,
                    component=None,
                    icon=None,
                    sort=0,
                    is_hidden=False,
                    permission=None,
                ),  # pyright: ignore[reportCallIssue]
            )
        menus = await menu_crud.get_multi(db_session)
        assert len(menus) >= 3


class TestCRUDMenuUpdate:
    """菜单更新测试"""

    async def test_update_menu(self, db_session: AsyncSession):
        """测试更新菜单"""
        menu = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="Old Title",
                name="OldName",
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )
        update_in = MenuUpdate(title="New Title")
        updated = await menu_crud.update(db_session, db_obj=menu, obj_in=update_in)

        assert updated.title == "New Title"
        assert updated.name == "OldName"


class TestCRUDMenuDelete:
    """菜单删除测试"""

    async def test_delete_menu(self, db_session: AsyncSession):
        """测试软删除"""
        menu = await menu_crud.create(
            db_session,
            obj_in=MenuCreate(
                title="Delete Menu",
                name="DelMenu",
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            ),  # pyright: ignore[reportCallIssue]
        )
        await menu_crud.remove(db_session, id=menu.id)
        assert await menu_crud.get(db_session, id=menu.id) is None
