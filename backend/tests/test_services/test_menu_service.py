"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_menu_service.py
@DateTime: 2025-12-30 21:35:00
@Docs: Menu Service 业务逻辑测试.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MenuType
from app.core.exceptions import NotFoundException

# Import actual crud instance or mock
from app.crud.crud_menu import menu as menu_crud_instance
from app.schemas.menu import MenuCreate, MenuUpdate
from app.services.menu_service import MenuService


@pytest.fixture
def service(db_session: AsyncSession):
    return MenuService(db_session, menu_crud_instance)


class TestMenuServiceCreate:
    async def test_create_menu(self, service: MenuService):
        menu_in = MenuCreate(
            title="Svc Menu",
            name="SvcMenu",
            type=MenuType.CATALOG,
            parent_id=None,
            path=None,
            component=None,
            icon=None,
            sort=0,
            is_hidden=False,
            permission=None,
        )
        menu = await service.create_menu(obj_in=menu_in)
        assert menu.title == "Svc Menu"


class TestMenuServiceUpdate:
    async def test_update_menu_not_found(self, service: MenuService):
        with pytest.raises(NotFoundException):
            await service.update_menu(id=uuid.uuid4(), obj_in=MenuUpdate(title="X"))

    async def test_update_menu_success(self, service: MenuService):
        menu = await service.create_menu(
            obj_in=MenuCreate(
                title="ToUp",
                name="ToUp",
                type=MenuType.CATALOG,
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            )
        )
        updated = await service.update_menu(id=menu.id, obj_in=MenuUpdate(title="Updated"))
        assert updated.title == "Updated"


class TestMenuServiceDelete:
    async def test_delete_menu_not_found(self, service: MenuService):
        with pytest.raises(NotFoundException):
            await service.delete_menu(id=uuid.uuid4())

    async def test_delete_menu_success(self, service: MenuService):
        menu = await service.create_menu(
            obj_in=MenuCreate(
                title="ToDel",
                name="ToDel",
                type=MenuType.CATALOG,
                parent_id=None,
                path=None,
                component=None,
                icon=None,
                sort=0,
                is_hidden=False,
                permission=None,
            )
        )
        deleted = await service.delete_menu(id=menu.id)
        assert deleted.is_deleted is True
