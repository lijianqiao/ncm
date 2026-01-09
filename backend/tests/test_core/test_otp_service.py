"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_otp_service.py
@DateTime: 2026-01-09 17:00:00
@Docs: OTP 服务模块单元测试。
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pyotp
import pytest

from app.core.encryption import encrypt_otp_seed, encrypt_password
from app.core.enums import AuthType
from app.core.exceptions import DeviceCredentialNotFoundException, OTPRequiredException
from app.core.otp_service import OTPService, otp_service


class TestTOTPGeneration:
    """测试 TOTP 生成功能。"""

    def test_generate_totp_valid_seed(self):
        """测试从有效种子生成 TOTP。"""
        # 创建一个有效的 Base32 种子
        seed = pyotp.random_base32()
        encrypted_seed = encrypt_otp_seed(seed)

        service = OTPService()
        otp_code = service.generate_totp(encrypted_seed)

        # 验证生成的验证码是 6 位数字
        assert len(otp_code) == 6
        assert otp_code.isdigit()

        # 验证生成的验证码与 PyOTP 直接生成的一致
        expected = pyotp.TOTP(seed).now()
        assert otp_code == expected

    def test_verify_totp_correct(self):
        """测试验证正确的 TOTP。"""
        seed = pyotp.random_base32()
        encrypted_seed = encrypt_otp_seed(seed)

        service = OTPService()
        otp_code = service.generate_totp(encrypted_seed)

        # 验证应该通过
        assert service.verify_totp(encrypted_seed, otp_code) is True

    def test_verify_totp_incorrect(self):
        """测试验证错误的 TOTP。"""
        seed = pyotp.random_base32()
        encrypted_seed = encrypt_otp_seed(seed)

        service = OTPService()

        # 使用错误的验证码
        assert service.verify_totp(encrypted_seed, "000000") is False


class TestOTPCache:
    """测试 OTP 缓存功能。"""

    @pytest.fixture
    def mock_redis(self):
        """创建 Mock Redis 客户端。"""
        mock = AsyncMock()
        mock.setex = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.ttl = AsyncMock(return_value=-2)
        mock.delete = AsyncMock(return_value=1)
        return mock

    @pytest.mark.asyncio
    async def test_cache_otp_success(self, mock_redis):
        """测试缓存 OTP 成功。"""
        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService(cache_ttl=60)
            dept_id = uuid4()
            device_group = "core"
            otp_code = "123456"

            ttl = await service.cache_otp(dept_id, device_group, otp_code)

            assert ttl == 60
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args[0]
            assert f"{dept_id}" in call_args[0]
            assert device_group in call_args[0]

    @pytest.mark.asyncio
    async def test_cache_otp_redis_unavailable(self):
        """测试 Redis 不可用时缓存 OTP。"""
        with patch("app.core.otp_service.redis_client", None):
            service = OTPService()
            ttl = await service.cache_otp(uuid4(), "core", "123456")
            assert ttl == 0

    @pytest.mark.asyncio
    async def test_get_cached_otp_hit(self, mock_redis):
        """测试获取缓存的 OTP - 命中。"""
        mock_redis.get = AsyncMock(return_value="654321")

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()
            otp = await service.get_cached_otp(uuid4(), "distribution")

            assert otp == "654321"

    @pytest.mark.asyncio
    async def test_get_cached_otp_miss(self, mock_redis):
        """测试获取缓存的 OTP - 未命中。"""
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()
            otp = await service.get_cached_otp(uuid4(), "access")

            assert otp is None

    @pytest.mark.asyncio
    async def test_get_otp_ttl(self, mock_redis):
        """测试获取 OTP 缓存 TTL。"""
        mock_redis.ttl = AsyncMock(return_value=45)

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()
            ttl = await service.get_otp_ttl(uuid4(), "core")

            assert ttl == 45

    @pytest.mark.asyncio
    async def test_invalidate_otp(self, mock_redis):
        """测试使 OTP 缓存失效。"""
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()
            result = await service.invalidate_otp(uuid4(), "core")

            assert result is True
            mock_redis.delete.assert_called_once()


class TestDeviceCredential:
    """测试设备凭据获取功能。"""

    @pytest.mark.asyncio
    async def test_get_credential_static(self):
        """测试获取静态密码设备凭据。"""
        service = OTPService()
        password = "my_static_password"
        encrypted_password = encrypt_password(password)

        credential = await service.get_credential_for_static_device(
            username="admin",
            encrypted_password=encrypted_password,
        )

        assert credential.username == "admin"
        assert credential.password == password
        assert credential.auth_type == AuthType.STATIC

    @pytest.mark.asyncio
    async def test_get_credential_otp_seed(self):
        """测试获取 OTP 种子设备凭据。"""
        service = OTPService()
        seed = pyotp.random_base32()
        encrypted_seed = encrypt_otp_seed(seed)

        credential = await service.get_credential_for_otp_seed_device(
            username="network_admin",
            encrypted_seed=encrypted_seed,
        )

        assert credential.username == "network_admin"
        assert len(credential.password) == 6
        assert credential.password.isdigit()
        assert credential.auth_type == AuthType.OTP_SEED

        # 验证生成的 OTP 是正确的
        expected = pyotp.TOTP(seed).now()
        assert credential.password == expected

    @pytest.fixture
    def mock_redis_with_otp(self):
        """创建带有缓存 OTP 的 Mock Redis。"""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value="789012")
        return mock

    @pytest.mark.asyncio
    async def test_get_credential_otp_manual_cached(self, mock_redis_with_otp):
        """测试获取手动 OTP 设备凭据 - 缓存存在。"""
        with patch("app.core.otp_service.redis_client", mock_redis_with_otp):
            service = OTPService()
            dept_id = uuid4()

            credential = await service.get_credential_for_otp_manual_device(
                username="ops_user",
                dept_id=dept_id,
                device_group="core",
            )

            assert credential.username == "ops_user"
            assert credential.password == "789012"
            assert credential.auth_type == AuthType.OTP_MANUAL

    @pytest.mark.asyncio
    async def test_get_credential_otp_manual_not_cached(self):
        """测试获取手动 OTP 设备凭据 - 缓存不存在，抛出异常。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()
            dept_id = uuid4()

            with pytest.raises(OTPRequiredException) as exc_info:
                await service.get_credential_for_otp_manual_device(
                    username="ops_user",
                    dept_id=dept_id,
                    device_group="distribution",
                    failed_devices=["10.0.0.1", "10.0.0.2"],
                )

            assert exc_info.value.dept_id == dept_id
            assert exc_info.value.device_group == "distribution"
            assert exc_info.value.failed_devices == ["10.0.0.1", "10.0.0.2"]
            assert exc_info.value.code == 428


class TestUnifiedCredentialAPI:
    """测试统一凭据获取 API。"""

    @pytest.mark.asyncio
    async def test_get_device_credential_static(self):
        """测试统一 API - 静态密码。"""
        service = OTPService()
        encrypted_password = encrypt_password("secret123")

        credential = await service.get_device_credential(
            auth_type=AuthType.STATIC,
            username="admin",
            password_or_seed=encrypted_password,
        )

        assert credential.auth_type == AuthType.STATIC
        assert credential.password == "secret123"

    @pytest.mark.asyncio
    async def test_get_device_credential_otp_seed(self):
        """测试统一 API - OTP 种子。"""
        service = OTPService()
        seed = pyotp.random_base32()
        encrypted_seed = encrypt_otp_seed(seed)

        credential = await service.get_device_credential(
            auth_type=AuthType.OTP_SEED,
            username="network",
            password_or_seed=encrypted_seed,
        )

        assert credential.auth_type == AuthType.OTP_SEED
        assert len(credential.password) == 6

    @pytest.mark.asyncio
    async def test_get_device_credential_otp_manual(self):
        """测试统一 API - 手动 OTP。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="111222")

        with patch("app.core.otp_service.redis_client", mock_redis):
            service = OTPService()

            credential = await service.get_device_credential(
                auth_type=AuthType.OTP_MANUAL,
                username="ops",
                dept_id=uuid4(),
                device_group="access",
            )

            assert credential.auth_type == AuthType.OTP_MANUAL
            assert credential.password == "111222"

    @pytest.mark.asyncio
    async def test_get_device_credential_missing_password(self):
        """测试统一 API - 缺少密码/种子。"""
        service = OTPService()

        with pytest.raises(DeviceCredentialNotFoundException):
            await service.get_device_credential(
                auth_type=AuthType.STATIC,
                username="admin",
                password_or_seed=None,
            )

    @pytest.mark.asyncio
    async def test_get_device_credential_missing_dept_id(self):
        """测试统一 API - 手动 OTP 缺少部门 ID。"""
        service = OTPService()

        with pytest.raises(DeviceCredentialNotFoundException):
            await service.get_device_credential(
                auth_type=AuthType.OTP_MANUAL,
                username="ops",
                dept_id=None,
                device_group="core",
            )


class TestOTPServiceSingleton:
    """测试 OTP 服务单例。"""

    def test_singleton_instance(self):
        """测试全局单例实例。"""
        assert otp_service is not None
        assert isinstance(otp_service, OTPService)

    def test_default_cache_ttl(self):
        """测试默认缓存 TTL。"""
        assert otp_service.cache_ttl == 60
