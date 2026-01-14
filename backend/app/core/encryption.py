"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: encryption.py
@DateTime: 2026-01-09 16:00:00
@Docs: AES-256-GCM 凭据加密模块。

用于保护设备静态密码和 OTP 种子，采用双密钥体系：
- NCM_CREDENTIAL_KEY: 静态密码加密
- NCM_OTP_SEED_KEY: OTP 种子加密
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.exceptions import BadRequestException

# AES-256-GCM 参数
AES_KEY_LENGTH = 32  # 256 bits
GCM_IV_LENGTH = 12  # 96 bits (推荐值)
GCM_TAG_LENGTH = 16  # 128 bits


class EncryptionError(BadRequestException):
    """加密/解密异常。"""

    def __init__(self, message: str = "加密操作失败"):
        super().__init__(message=message)


class DecryptionError(BadRequestException):
    """解密异常。"""

    def __init__(self, message: str = "解密操作失败"):
        super().__init__(message=message)


def _normalize_key(key: str) -> bytes:
    """
    将字符串密钥标准化为 32 字节。

    支持两种格式：
    1. 直接 UTF-8 字符串（需要正好 32 字节）
    2. Hex 编码字符串（64 个十六进制字符 = 32 字节）

    Args:
        key: 密钥字符串

    Returns:
        32 字节的密钥

    Raises:
        EncryptionError: 密钥格式无效
    """
    key = key.strip()
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()

    # 尝试 hex 解码
    if len(key) == 64:
        try:
            key_bytes = bytes.fromhex(key)
            if len(key_bytes) == AES_KEY_LENGTH:
                return key_bytes
        except ValueError:
            pass

    # UTF-8 编码
    key_bytes = key.encode(encoding="utf-8")
    if len(key_bytes) == AES_KEY_LENGTH:
        return key_bytes

    raise EncryptionError(
        f"密钥长度无效：需要 {AES_KEY_LENGTH} 字节，当前 {len(key_bytes)} 字节。"
        f"可使用 32 字符 UTF-8 字符串或 64 字符 Hex 编码。"
    )


def encrypt_credential(plaintext: str, key: str) -> str:
    """
    使用 AES-256-GCM 加密明文。

    Args:
        plaintext: 要加密的明文
        key: 加密密钥（32 字节字符串或 64 字符 Hex）

    Returns:
        Base64 编码的密文（格式：iv + ciphertext + tag）

    Raises:
        EncryptionError: 加密失败
    """
    if not plaintext:
        raise EncryptionError(message="明文不能为空")

    try:
        key_bytes = _normalize_key(key)
        aesgcm = AESGCM(key_bytes)

        # 生成随机 IV
        iv = os.urandom(GCM_IV_LENGTH)

        # 加密（AESGCM.encrypt 返回 ciphertext + tag）
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext_with_tag = aesgcm.encrypt(iv, plaintext_bytes, None)

        # 组合：iv + ciphertext + tag
        combined = iv + ciphertext_with_tag

        # Base64 编码
        return base64.b64encode(combined).decode("utf-8")

    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"加密失败: {e!s}") from e


def decrypt_credential(ciphertext: str, key: str) -> str:
    """
    使用 AES-256-GCM 解密密文。

    Args:
        ciphertext: Base64 编码的密文
        key: 解密密钥（需与加密时相同）

    Returns:
        解密后的明文

    Raises:
        DecryptionError: 解密失败（密钥错误、数据被篡改等）
    """
    if not ciphertext:
        raise DecryptionError("密文不能为空")

    try:
        key_bytes = _normalize_key(key)
        aesgcm = AESGCM(key_bytes)

        # Base64 解码
        combined = base64.b64decode(ciphertext)

        # 验证长度（至少需要 iv + tag）
        min_length = GCM_IV_LENGTH + GCM_TAG_LENGTH
        if len(combined) < min_length:
            raise DecryptionError("密文格式无效：长度不足")

        # 分离 iv 和 ciphertext_with_tag
        iv = combined[:GCM_IV_LENGTH]
        ciphertext_with_tag = combined[GCM_IV_LENGTH:]

        # 解密
        plaintext_bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)

        return plaintext_bytes.decode("utf-8")

    except DecryptionError:
        raise
    except EncryptionError as e:
        raise DecryptionError("密钥格式无效") from e
    except Exception as e:
        raise DecryptionError(f"解密失败: {e!s}") from e


# ===== 便捷函数：静态密码加密 =====


def encrypt_password(plaintext: str) -> str:
    """
    加密静态密码（使用 NCM_CREDENTIAL_KEY）。

    Args:
        plaintext: 明文密码

    Returns:
        Base64 编码的密文
    """
    return encrypt_credential(plaintext, settings.NCM_CREDENTIAL_KEY)


def decrypt_password(ciphertext: str) -> str:
    """
    解密静态密码（使用 NCM_CREDENTIAL_KEY）。

    Args:
        ciphertext: 加密后的密码

    Returns:
        明文密码
    """
    return decrypt_credential(ciphertext, settings.NCM_CREDENTIAL_KEY)


# ===== 便捷函数：OTP 种子加密 =====


def encrypt_otp_seed(plaintext: str) -> str:
    """
    加密 OTP 种子（使用 NCM_OTP_SEED_KEY）。

    Args:
        plaintext: 明文 OTP 种子

    Returns:
        Base64 编码的密文
    """
    return encrypt_credential(plaintext, settings.NCM_OTP_SEED_KEY)


def decrypt_otp_seed(ciphertext: str) -> str:
    """
    解密 OTP 种子（使用 NCM_OTP_SEED_KEY）。

    Args:
        ciphertext: 加密后的 OTP 种子

    Returns:
        明文 OTP 种子
    """
    return decrypt_credential(ciphertext, settings.NCM_OTP_SEED_KEY)


def encrypt_snmp_secret(plaintext: str) -> str:
    return encrypt_credential(plaintext, settings.NCM_SNMP_KEY)


def decrypt_snmp_secret(ciphertext: str) -> str:
    return decrypt_credential(ciphertext, settings.NCM_SNMP_KEY)


# ===== 工具函数 =====


def generate_encryption_key() -> str:
    """
    生成随机 AES-256 密钥（Hex 格式）。

    可用于生成配置中的 NCM_CREDENTIAL_KEY 或 NCM_OTP_SEED_KEY。

    Returns:
        64 字符 Hex 编码的密钥
    """
    return os.urandom(AES_KEY_LENGTH).hex()
