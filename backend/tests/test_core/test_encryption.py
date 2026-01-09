"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_encryption.py
@DateTime: 2026-01-09 16:00:00
@Docs: AES-256-GCM 加密模块单元测试。
"""

import os

import pytest

from app.core.encryption import (
    DecryptionError,
    EncryptionError,
    decrypt_credential,
    decrypt_otp_seed,
    decrypt_password,
    encrypt_credential,
    encrypt_otp_seed,
    encrypt_password,
    generate_encryption_key,
)


class TestEncryptCredential:
    """测试通用加密/解密函数。"""

    # 有效的 32 字节密钥（确保正好 32 个 ASCII 字符）
    VALID_KEY_UTF8 = "this_is_a_32_byte_test_key_ok!!!"  # 32 chars
    VALID_KEY_HEX = os.urandom(32).hex()

    def test_encrypt_decrypt_roundtrip_utf8_key(self):
        """测试使用 UTF-8 密钥的加密解密往返。"""
        plaintext = "my_secret_password_123"
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY_UTF8)
        decrypted = decrypt_credential(ciphertext, self.VALID_KEY_UTF8)
        assert decrypted == plaintext

    def test_encrypt_decrypt_roundtrip_hex_key(self):
        """测试使用 Hex 密钥的加密解密往返。"""
        plaintext = "another_secret_value"
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY_HEX)
        decrypted = decrypt_credential(ciphertext, self.VALID_KEY_HEX)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self):
        """测试每次加密产生不同的密文（因为随机 IV）。"""
        plaintext = "same_input"
        ciphertext1 = encrypt_credential(plaintext, self.VALID_KEY_UTF8)
        ciphertext2 = encrypt_credential(plaintext, self.VALID_KEY_UTF8)
        assert ciphertext1 != ciphertext2

    def test_unicode_plaintext(self):
        """测试 Unicode 明文加密。"""
        plaintext = "密码测试123🔐"
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY_UTF8)
        decrypted = decrypt_credential(ciphertext, self.VALID_KEY_UTF8)
        assert decrypted == plaintext

    def test_long_plaintext(self):
        """测试长明文加密。"""
        plaintext = "x" * 10000
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY_UTF8)
        decrypted = decrypt_credential(ciphertext, self.VALID_KEY_UTF8)
        assert decrypted == plaintext


class TestEncryptionErrors:
    """测试加密异常情况。"""

    VALID_KEY = "this_is_a_32_byte_test_key_ok!!!"  # 32 chars

    def test_encrypt_empty_plaintext(self):
        """测试空明文加密。"""
        with pytest.raises(EncryptionError):
            encrypt_credential("", self.VALID_KEY)

    def test_encrypt_invalid_key_length(self):
        """测试无效密钥长度。"""
        with pytest.raises(EncryptionError, match="密钥长度无效"):
            encrypt_credential("test", "short_key")


class TestDecryptionErrors:
    """测试解密异常情况。"""

    VALID_KEY = "this_is_a_32_byte_test_key_ok!!!"  # 32 chars
    WRONG_KEY = "wrong_key_but_32_bytes_length!!!"  # 32 chars

    def test_decrypt_empty_ciphertext(self):
        """测试空密文解密。"""
        with pytest.raises(DecryptionError, match="密文不能为空"):
            decrypt_credential("", self.VALID_KEY)

    def test_decrypt_invalid_base64(self):
        """测试无效 Base64 密文。"""
        with pytest.raises(DecryptionError, match="解密失败"):
            decrypt_credential("not_valid_base64!!!", self.VALID_KEY)

    def test_decrypt_wrong_key(self):
        """测试使用错误密钥解密。"""
        plaintext = "secret"
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY)
        with pytest.raises(DecryptionError, match="解密失败"):
            decrypt_credential(ciphertext, self.WRONG_KEY)

    def test_decrypt_tampered_ciphertext(self):
        """测试篡改的密文解密（GCM 认证失败）。"""
        plaintext = "secret"
        ciphertext = encrypt_credential(plaintext, self.VALID_KEY)
        # 篡改密文的最后一个字符
        tampered = ciphertext[:-1] + ("A" if ciphertext[-1] != "A" else "B")
        with pytest.raises(DecryptionError):
            decrypt_credential(tampered, self.VALID_KEY)

    def test_decrypt_too_short_ciphertext(self):
        """测试过短的密文。"""
        import base64

        short_data = base64.b64encode(b"short").decode()
        with pytest.raises(DecryptionError, match="长度不足"):
            decrypt_credential(short_data, self.VALID_KEY)


class TestKeyIsolation:
    """测试密钥隔离性。"""

    KEY1 = "key_one_32_bytes_for_testing!!!!"  # 32 chars
    KEY2 = "key_two_32_bytes_for_testing!!!!"  # 32 chars

    def test_different_keys_cannot_decrypt(self):
        """测试不同密钥无法互相解密。"""
        plaintext = "secret_data"

        ciphertext1 = encrypt_credential(plaintext, self.KEY1)
        ciphertext2 = encrypt_credential(plaintext, self.KEY2)

        # 各自可以解密
        assert decrypt_credential(ciphertext1, self.KEY1) == plaintext
        assert decrypt_credential(ciphertext2, self.KEY2) == plaintext

        # 交叉解密应失败
        with pytest.raises(DecryptionError):
            decrypt_credential(ciphertext1, self.KEY2)

        with pytest.raises(DecryptionError):
            decrypt_credential(ciphertext2, self.KEY1)


class TestConvenienceFunctions:
    """测试便捷函数（使用配置中的密钥）。"""

    def test_encrypt_decrypt_password(self):
        """测试静态密码加密解密。"""
        plaintext = "device_password_123"
        ciphertext = encrypt_password(plaintext)
        decrypted = decrypt_password(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_decrypt_otp_seed(self):
        """测试 OTP 种子加密解密。"""
        # TOTP 种子通常是 Base32 编码的字符串
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext = encrypt_otp_seed(plaintext)
        decrypted = decrypt_otp_seed(ciphertext)
        assert decrypted == plaintext

    def test_password_and_otp_use_different_keys(self):
        """测试密码和 OTP 种子使用不同密钥。"""
        plaintext = "same_value"

        password_cipher = encrypt_password(plaintext)
        otp_cipher = encrypt_otp_seed(plaintext)

        # 不能交叉解密
        with pytest.raises(DecryptionError):
            decrypt_password(otp_cipher)

        with pytest.raises(DecryptionError):
            decrypt_otp_seed(password_cipher)


class TestGenerateEncryptionKey:
    """测试密钥生成函数。"""

    def test_generate_key_format(self):
        """测试生成的密钥格式。"""
        key = generate_encryption_key()
        assert len(key) == 64  # 32 字节 = 64 Hex 字符
        # 应该是有效的 Hex
        bytes.fromhex(key)

    def test_generate_key_uniqueness(self):
        """测试生成的密钥唯一性。"""
        keys = [generate_encryption_key() for _ in range(100)]
        assert len(set(keys)) == 100  # 所有密钥应该不同

    def test_generated_key_works(self):
        """测试生成的密钥可用于加解密。"""
        key = generate_encryption_key()
        plaintext = "test_with_generated_key"
        ciphertext = encrypt_credential(plaintext, key)
        decrypted = decrypt_credential(ciphertext, key)
        assert decrypted == plaintext
