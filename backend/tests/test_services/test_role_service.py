"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_role_service.py
@DateTime: 2025-12-30 21:10:00
@Docs: Role Service 业务逻辑测试.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException

# 由于 conftest 没有导出 role_crud fixture，我们在 test file 里定义一个，
# 或者直接实例化。
from app.crud.crud_menu import menu as menu_crud_instance
from app.crud.crud_role import role as role_crud_instance
from app.schemas.role import RoleCreate, RoleUpdate
from app.services.role_service import RoleService


@pytest.fixture
def role_service(db_session: AsyncSession, role_crud):
    """创建 RoleService 实例"""
    # 这里 mock authentication? 不需要，Service 层不感知 Auth。
    # 只需要注入 db 和 crud。
    # 我们需要在 conftest 或者这里 mock role_crud 吗？
    # 集成测试最好用真实的 crud，这样能测到数据库约束。
    return RoleService(db_session, role_crud, menu_crud_instance)


@pytest.fixture
def service(db_session: AsyncSession):
    return RoleService(db_session, role_crud_instance, menu_crud_instance)


class TestRoleServiceCreate:
    """创建角色业务测试"""

    async def test_create_role_success(self, service: RoleService):
        """测试成功创建角色"""
        role_in = RoleCreate(name="Service Role", code="svc_role", description=None, sort=0)
        role = await service.create_role(obj_in=role_in)
        assert role.code == "svc_role"

    async def test_create_role_duplicate_code(self, service: RoleService):
        """测试重复编码报错"""
        role_in = RoleCreate(name="Role 1", code="uniq_code", description=None, sort=0)
        await service.create_role(obj_in=role_in)

        # 尝试使用相同 code 创建
        role_in_2 = RoleCreate(name="Role 2", code="uniq_code", description=None, sort=0)
        with pytest.raises(BadRequestException) as exc:
            await service.create_role(obj_in=role_in_2)
        assert "角色编码已存在" in exc.value.message


class TestRoleServiceUpdate:
    """更新角色业务测试"""

    async def test_update_role_success(self, service: RoleService):
        role_in = RoleCreate(name="To Update", code="to_update", description=None, sort=0)
        role = await service.create_role(obj_in=role_in)

        update_in = RoleUpdate(name="Updated Name")  # pyright: ignore
        updated = await service.update_role(id=role.id, obj_in=update_in)
        assert updated.name == "Updated Name"

    async def test_update_role_not_found(self, service: RoleService):
        """更新不存在的角色"""
        with pytest.raises(NotFoundException):
            await service.update_role(
                id=uuid.uuid4(),
                obj_in=RoleUpdate(name="X"),  # pyright: ignore
            )

    async def test_update_role_duplicate_code(self, service: RoleService):
        """更新时编码冲突检查"""
        # 创建两个角色
        await service.create_role(obj_in=RoleCreate(name="R1", code="c1", description=None, sort=0))
        r2 = await service.create_role(obj_in=RoleCreate(name="R2", code="c2", description=None, sort=0))

        # 尝试把 r2 的 code 改成 c1
        update_in = RoleUpdate(code="c1")  # pyright: ignore
        with pytest.raises(BadRequestException) as exc:
            await service.update_role(id=r2.id, obj_in=update_in)
        assert "角色编码被占用" in exc.value.message

    async def test_update_role_same_code(self, service: RoleService):
        """更新自己时不应报冲突"""
        r1 = await service.create_role(obj_in=RoleCreate(name="R1", code="c1", description=None, sort=0))

        # 把 r1 的 code 改成 c1 (没变)
        update_in = RoleUpdate(code="c1", name="New Name")  # pyright: ignore
        updated = await service.update_role(id=r1.id, obj_in=update_in)
        assert updated.name == "New Name"
        assert updated.code == "c1"


class TestRoleServiceDelete:
    """删除角色业务测试"""

    async def test_delete_role_not_found(self, service: RoleService):
        with pytest.raises(NotFoundException):
            await service.delete_role(id=uuid.uuid4())
