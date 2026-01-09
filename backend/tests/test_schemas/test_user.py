"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_user.py
@DateTime: 2025-12-30 16:35:00
@Docs: 用户 Schema 验证测试.
"""

import pytest
from pydantic import ValidationError

from app.schemas.user import (
    ChangePasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserUpdate,
)


class TestPasswordValidation:
    """密码强度验证测试"""

    def test_valid_complex_password(self):
        """测试有效的复杂密码"""
        user = UserCreate(  # pyright: ignore[reportCallIssue]
            username="testuser",
            phone="13800138000",
            password="Test@12345",
            email="test@example.com",
        )
        assert user.password == "Test@12345"

    def test_password_missing_uppercase(self):
        """测试缺少大写字母的密码"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="13800138000",
                password="test@12345",
                email="test@example.com",
            )
        assert "大写字母" in str(exc_info.value)

    def test_password_missing_lowercase(self):
        """测试缺少小写字母的密码"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="13800138000",
                password="TEST@12345",
                email="test@example.com",
            )
        assert "小写字母" in str(exc_info.value)

    def test_password_missing_digit(self):
        """测试缺少数字的密码"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="13800138000",
                password="Test@abcde",
                email="test@example.com",
            )
        assert "数字" in str(exc_info.value)

    def test_password_missing_special_char(self):
        """测试缺少特殊字符的密码"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="13800138000",
                password="Test123456",
                email="test@example.com",
            )
        assert "特殊字符" in str(exc_info.value)

    def test_password_too_short(self):
        """测试密码长度不足"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="13800138000",
                password="Te@1234",
                email="test@example.com",
            )
        assert "8 位" in str(exc_info.value)

    def test_change_password_request_validation(self):
        """测试修改密码请求验证"""
        req = ChangePasswordRequest(
            old_password="oldpass",
            new_password="New@12345",
        )
        assert req.new_password == "New@12345"

    def test_reset_password_request_validation(self):
        """测试重置密码请求验证"""
        req = ResetPasswordRequest(new_password="Reset@123")
        assert req.new_password == "Reset@123"


class TestPhoneValidation:
    """手机号验证测试"""

    def test_valid_phone_number(self):
        """测试有效手机号"""
        user = UserCreate(  # pyright: ignore[reportCallIssue]
            username="testuser",
            phone="13800138000",
            password="Test@12345",
            email="test@example.com",
        )
        # 应该格式化为 E.164 格式
        assert user.phone == "+8613800138000"

    def test_valid_phone_with_country_code(self):
        """测试带国家代码的手机号"""
        user = UserCreate(  # pyright: ignore[reportCallIssue]
            username="testuser",
            phone="+8613800138000",
            password="Test@12345",
            email="test@example.com",
        )
        assert user.phone == "+8613800138000"

    def test_invalid_phone_number(self):
        """测试无效手机号"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(  # pyright: ignore[reportCallIssue]
                username="testuser",
                phone="12345",
                password="Test@12345",
                email="test@example.com",
            )
        assert "手机号" in str(exc_info.value)


class TestUserUpdate:
    """用户更新 Schema 测试"""

    def test_partial_update(self):
        """测试部分更新"""
        update = UserUpdate(nickname="新昵称")
        assert update.nickname == "新昵称"
