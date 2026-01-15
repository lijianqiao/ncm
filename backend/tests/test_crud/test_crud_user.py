"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_crud_user.py
@DateTime: 2025-12-30 16:40:00
@Docs: 用户 CRUD 操作测试.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_user import CRUDUser
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


@pytest.fixture
def user_crud() -> CRUDUser:
    """创建 CRUDUser 实例"""
    return CRUDUser(User)


class TestCRUDUserCreate:
    """用户创建测试"""

    async def test_create_user(self, db_session: AsyncSession, user_crud: CRUDUser):
        """测试创建用户"""
        user_in = UserCreate(  # pyright: ignore[reportCallIssue]
            username="newuser",
            phone="13900139000",
            password="Test@12345",
            email="new@example.com",
        )
        user = await user_crud.create(db_session, obj_in=user_in)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        # 密码应该被哈希
        assert user.password != "Test@12345"
        assert len(user.password) > 20


class TestCRUDUserGet:
    """用户查询测试"""

    async def test_get_user_by_id(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试通过 ID 获取用户"""
        user = await user_crud.get(db_session, id=test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    async def test_get_user_not_found(self, db_session: AsyncSession, user_crud: CRUDUser):
        """测试获取不存在的用户"""
        user = await user_crud.get(db_session, id=uuid.uuid4())
        assert user is None

    async def test_get_by_username(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试通过用户名获取用户"""
        user = await user_crud.get_by_username(db_session, username=test_user.username)

        assert user is not None
        assert user.username == test_user.username

    async def test_get_by_email(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试通过邮箱获取用户"""
        assert test_user.email is not None
        user = await user_crud.get_by_email(db_session, email=test_user.email)

        assert user is not None
        assert user.email == test_user.email

    async def test_get_by_phone(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试通过手机号获取用户"""
        user = await user_crud.get_by_phone(db_session, phone=test_user.phone)

        assert user is not None
        assert user.phone == test_user.phone


class TestCRUDUserUpdate:
    """用户更新测试"""

    async def test_update_user(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试更新用户"""
        update_data = UserUpdate(nickname="更新后的昵称")
        updated_user = await user_crud.update(db_session, db_obj=test_user, obj_in=update_data)

        assert updated_user.nickname == "更新后的昵称"
        assert updated_user.username == test_user.username

    async def test_update_user_password(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试更新用户密码（应自动哈希）"""
        old_password = test_user.password
        update_data = {"password": "NewPass@123"}
        updated_user = await user_crud.update(db_session, db_obj=test_user, obj_in=update_data)

        # 密码应该被哈希，且不同于旧密码和明文
        assert updated_user.password != old_password
        assert updated_user.password != "NewPass@123"


class TestCRUDUserDelete:
    """用户删除测试"""

    async def test_soft_delete_user(self, db_session: AsyncSession, user_crud: CRUDUser, test_user: User):
        """测试软删除用户"""
        user_id = test_user.id

        success_count, failed_ids = await user_crud.batch_remove(db_session, ids=[user_id])
        assert success_count == 1
        assert failed_ids == []

        # 软删除后通过 get 应该查不到
        user = await user_crud.get(db_session, id=user_id)
        assert user is None

        deleted_items, _ = await user_crud.get_multi_deleted_paginated(db_session, page=1, page_size=50)
        assert any(x.id == user_id for x in deleted_items)

    async def test_batch_remove(self, db_session: AsyncSession, user_crud: CRUDUser):
        """测试批量删除"""
        # 创建多个用户
        users = []
        for i in range(3):
            user_in = UserCreate(  # pyright: ignore[reportCallIssue]
                username=f"batchuser{i}",
                phone=f"1390013900{i}",
                password="Test@12345",
            )
            user = await user_crud.create(db_session, obj_in=user_in)
            users.append(user)

        # 批量删除
        ids = [u.id for u in users]
        success_count, failed_ids = await user_crud.batch_remove(db_session, ids=ids)

        assert success_count == 3
        assert len(failed_ids) == 0

        # 验证都已软删除
        for user_id in ids:
            user = await user_crud.get(db_session, id=user_id)
            assert user is None


class TestCRUDUserPagination:
    """用户分页测试"""

    async def test_get_multi_paginated(self, db_session: AsyncSession, user_crud: CRUDUser):
        """测试分页查询"""
        # 创建多个用户
        for i in range(5):
            user_in = UserCreate(  # pyright: ignore[reportCallIssue]
                username=f"pageuser{i}",
                phone=f"1380013800{i}",
                password="Test@12345",
            )
            await user_crud.create(db_session, obj_in=user_in)

        # 测试分页
        users, total = await user_crud.get_multi_paginated(db_session, page=1, page_size=2)

        assert len(users) == 2
        assert total == 5

    async def test_get_multi_paginated_second_page(self, db_session: AsyncSession, user_crud: CRUDUser):
        """测试第二页"""
        # 创建多个用户
        for i in range(5):
            user_in = UserCreate(  # pyright: ignore[reportCallIssue]
                username=f"page2user{i}",
                phone=f"1370013700{i}",
                password="Test@12345",
            )
            await user_crud.create(db_session, obj_in=user_in)

        users, total = await user_crud.get_multi_paginated(db_session, page=2, page_size=2)

        assert len(users) == 2
        assert total == 5
