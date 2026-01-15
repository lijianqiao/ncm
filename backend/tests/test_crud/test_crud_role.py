"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_crud_role.py
@DateTime: 2025-12-30 21:05:00
@Docs: Role CRUD 测试.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_role import role as role_crud
from app.models.rbac import Menu
from app.schemas.role import RoleCreate, RoleUpdate


@pytest.fixture
async def test_menu(db_session: AsyncSession) -> Menu:
    """创建一个测试菜单"""
    menu = Menu(title="测试菜单", name="TestMenu", path="/test", component="Layout", sort=1)
    db_session.add(menu)
    await db_session.commit()
    await db_session.refresh(menu)
    return menu


class TestCRUDRoleCreate:
    """角色创建测试"""

    async def test_create_role(self, db_session: AsyncSession):
        """测试创建基本角色"""
        role_in = RoleCreate(name="Test Role", code="test_role", description="Test Description", sort=0)
        role = await role_crud.create(db_session, obj_in=role_in)

        assert role.name == "Test Role"
        assert role.code == "test_role"
        assert role.id is not None

    async def test_create_role_then_bind_menus(self, db_session: AsyncSession, test_menu: Menu):
        """测试创建角色后绑定菜单"""
        role_in = RoleCreate(name="Menu Role", code="menu_role", description=None, sort=0)
        role = await role_crud.create(db_session, obj_in=role_in)

        await role_crud.update(db_session, db_obj=role, obj_in={"menu_ids": [test_menu.id]})

        assert role.code == "menu_role"
        # 验证关联
        # 注意：create 返回的对象可能没有加载 menus (取决于实现是否 refresh 并 eager load),
        # 但 crud_role.create 做了 refresh。
        # 由于我们用的是 selectinload，需要确保 session 里的状态正确。

        # 重新获取以确保加载关联
        stored_role = await role_crud.get(db_session, id=role.id)
        assert stored_role is not None
        assert len(stored_role.menus) == 1
        assert stored_role.menus[0].id == test_menu.id


class TestCRUDRoleGet:
    """角色查询测试"""

    async def test_get_role(self, db_session: AsyncSession):
        """测试获取角色"""
        role_in = RoleCreate(name="Get Role", code="get_role", description=None, sort=0)
        created_role = await role_crud.create(db_session, obj_in=role_in)

        stored_role = await role_crud.get(db_session, id=created_role.id)
        assert stored_role is not None
        assert stored_role.id == created_role.id
        assert stored_role.code == "get_role"

    async def test_get_by_code(self, db_session: AsyncSession):
        """测试通过编码获取角色"""
        role_in = RoleCreate(name="Code Role", code="code_role", description=None, sort=0)
        await role_crud.create(db_session, obj_in=role_in)

        role = await role_crud.get_by_code(db_session, code="code_role")
        assert role is not None
        assert role.name == "Code Role"

    async def test_get_multi(self, db_session: AsyncSession):
        """测试获取角色列表"""
        # 清理之前的角色(如果需要，或者依赖事务回滚)
        # 这里的 db_session 是 function scoped，自带回滚/隔离。

        for i in range(3):
            await role_crud.create(
                db_session,
                obj_in=RoleCreate(name=f"Role {i}", code=f"role_{i}", description=None, sort=0),
            )
        roles, total = await role_crud.get_multi_paginated(db_session, page=1, page_size=10)
        # 注意：可能包含其他测试用例创建的数据，如果 fixture 隔离不够。
        # 但 function scope 通常意味着独立数据库状态（如果 rollback or drop_all）。
        # 我们的 fixture 先 create_all 后 drop_all，是隔离的。
        assert total >= 3
        assert len(roles) >= 3


class TestCRUDRoleUpdate:
    """角色更新测试"""

    async def test_update_role(self, db_session: AsyncSession):
        """测试更新角色字段"""
        role_in = RoleCreate(name="Update Role", code="update_role", description=None, sort=0)
        role = await role_crud.create(db_session, obj_in=role_in)

        update_data = RoleUpdate(name="New Name", description="Updated Desc")  # pyright: ignore
        updated_role = await role_crud.update(db_session, db_obj=role, obj_in=update_data)

        assert updated_role.name == "New Name"
        assert updated_role.description == "Updated Desc"
        assert updated_role.code == "update_role"

    async def test_update_role_menus(self, db_session: AsyncSession, test_menu: Menu):
        """测试更新角色菜单关联"""
        role_in = RoleCreate(name="Update Menu Role", code="update_menu_role", description=None, sort=0)
        role = await role_crud.create(db_session, obj_in=role_in)

        # 初始无菜单
        stored_role = await role_crud.get(db_session, id=role.id)
        assert stored_role is not None
        assert len(stored_role.menus) == 0

        # 更新关联
        await role_crud.update(db_session, db_obj=role, obj_in={"menu_ids": [test_menu.id]})

        # 验证
        stored_role = await role_crud.get(db_session, id=role.id)
        assert stored_role is not None
        assert len(stored_role.menus) == 1
        assert stored_role.menus[0].id == test_menu.id

        # 清除关联
        await role_crud.update(db_session, db_obj=role, obj_in={"menu_ids": []})

        stored_role = await role_crud.get(db_session, id=role.id)
        assert stored_role is not None
        assert len(stored_role.menus) == 0


class TestCRUDRoleDelete:
    """角色删除测试"""

    async def test_soft_delete_role(self, db_session: AsyncSession):
        """测试软删除"""
        role_in = RoleCreate(name="Delete Role", code="delete_role", description=None, sort=0)
        role = await role_crud.create(db_session, obj_in=role_in)

        success_count, failed_ids = await role_crud.batch_remove(db_session, ids=[role.id])
        assert success_count == 1
        assert failed_ids == []

        # 普通 get 应该查不到
        assert await role_crud.get(db_session, id=role.id) is None
        # get_by_code 也查不到
        assert await role_crud.get_by_code(db_session, code="delete_role") is None

        deleted_items, _ = await role_crud.get_multi_deleted_paginated(db_session, page=1, page_size=50)
        assert any(x.id == role.id for x in deleted_items)
