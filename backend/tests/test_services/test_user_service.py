"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_user_service.py
@DateTime: 2025-12-30 16:45:00
@Docs: 用户服务测试.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_role import role as role_crud
from app.crud.crud_user import CRUDUser
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService


@pytest.fixture
def user_service(db_session: AsyncSession) -> UserService:
    """创建 UserService 实例"""
    user_crud = CRUDUser(User)
    return UserService(db=db_session, user_crud=user_crud, role_crud=role_crud)


class TestUserServiceCreate:
    """用户创建服务测试"""

    async def test_create_user_success(self, user_service: UserService):
        """测试成功创建用户"""
        user_in = UserCreate(
            username="serviceuser",
            phone="13600136000",
            password="Test@12345",
            email="s@example.com",
            nickname=None,
            gender="o",
            is_active=True,
            is_superuser=False,
        )  # pyright: ignore[reportCallIssue]
        user = await user_service.create_user(obj_in=user_in)

        assert user.username == "serviceuser"
        assert user.email == "s@example.com"

    async def test_create_user_duplicate_username(self, user_service: UserService, test_user: User):
        """测试重复用户名"""
        user_in = UserCreate(
            username=test_user.username,  # 使用已存在的用户名
            phone="13600136001",
            password="Test@12345",
            email="dup_u@ex.com",
            nickname=None,
            gender="o",
            is_active=True,
            is_superuser=False,
        )  # pyright: ignore[reportCallIssue]

        with pytest.raises(BadRequestException) as exc_info:
            await user_service.create_user(obj_in=user_in)

        assert "用户名" in str(exc_info.value.message)

    async def test_create_user_duplicate_phone(self, user_service: UserService, test_user: User):
        """测试重复手机号"""
        user_in = UserCreate(
            username="newuser",
            phone=test_user.phone,  # 使用 test_user 的手机号
            password="Test@123456",  # Fix password length
            email="new_u@ex.com",
            nickname=None,
            gender="o",
            is_active=True,
            is_superuser=False,
        )  # pyright: ignore[reportCallIssue]

        with pytest.raises(BadRequestException) as exc_info:
            await user_service.create_user(obj_in=user_in)

        assert "手机号" in str(exc_info.value.message)


class TestUserServicePassword:
    """密码操作服务测试"""

    async def test_change_password_success(self, user_service: UserService, test_user: User):
        """测试成功修改密码"""
        user = await user_service.change_password(
            user_id=test_user.id,
            old_password="Test@123456",
            new_password="NewPass@789",
        )

        assert user is not None

    async def test_change_password_wrong_old(self, user_service: UserService, test_user: User):
        """测试旧密码错误"""
        with pytest.raises(BadRequestException) as exc_info:
            await user_service.change_password(
                user_id=test_user.id,
                old_password="wrongpassword",
                new_password="NewPass@789",
            )

        assert "旧密码" in str(exc_info.value.message)

    async def test_reset_password_success(self, user_service: UserService, test_user: User):
        """测试管理员重置密码"""
        user = await user_service.reset_password(
            user_id=test_user.id,
            new_password="Reset@12345",
        )

        assert user is not None


class TestUserServiceUpdate:
    """用户更新服务测试"""

    async def test_update_user_success(self, user_service: UserService, test_user: User):
        """测试成功更新用户"""
        user = await user_service.update_user(
            user_id=test_user.id,
            obj_in=UserUpdate(nickname="新昵称"),
        )

        assert user.nickname == "新昵称"

    async def test_update_user_not_found(self, user_service: UserService):
        """测试更新不存在的用户"""
        import uuid

        with pytest.raises(NotFoundException):
            await user_service.update_user(
                user_id=uuid.uuid4(),
                obj_in=UserUpdate(nickname="新昵称"),
            )


class TestUserServiceBatchDelete:
    """批量删除服务测试"""

    async def test_batch_delete_success(self, user_service: UserService, db_session: AsyncSession):
        """测试批量删除成功"""
        # 先创建用户
        users = []
        for i in range(3):
            user_in = UserCreate(
                username=f"batch_{i}",
                phone=f"1350013500{i}",
                password="Test@12345",
                email=f"b{i}@ex.com",
                nickname=None,
                gender="o",
                is_active=True,
                is_superuser=False,
            )  # pyright: ignore[reportCallIssue]
            user = await user_service.create_user(obj_in=user_in)
            users.append(user)

        await db_session.commit()

        # 批量删除
        ids = [u.id for u in users]
        success_count, failed_ids = await user_service.batch_delete_users(ids=ids)

        assert success_count == 3
        assert len(failed_ids) == 0
