"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: security.py
@DateTime: 2025-12-30 11:55:00
@Docs: 安全工具（密码哈希、JWT生成）.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# 类型别名
type TokenType = Literal["access", "refresh"]

password_context = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码。

    Args:
        plain_password: 原始密码
        hashed_password: 哈希后的密码

    Returns:
        bool: 验证结果
    """
    return password_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希值。

    Args:
        password: 原始密码

    Returns:
        str: 哈希后的密码
    """
    return password_context.hash(password)


def _create_token(
    subject: str | Any,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
) -> str:
    """
    创建 JWT Token 的通用函数。

    Args:
        subject: Token 主体（通常是用户 ID）
        token_type: Token 类型（"access" 或 "refresh"）
        expires_delta: 自定义过期时间

    Returns:
        str: 编码后的 JWT Token
    """
    # 根据 token 类型确定默认过期时间
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        default_expires = (
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            if token_type == "access"
            else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        expire = datetime.now(UTC) + default_expires

    now = datetime.now(UTC)
    to_encode = {
        "exp": expire,
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "jti": uuid4().hex,
        "sub": str(subject),
        "type": token_type,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """创建 Access Token。

    Args:
        subject: Token 主体（通常是用户 ID）
        expires_delta: 自定义过期时间

    Returns:
        str: 编码后的 Access Token
    """
    return _create_token(subject, "access", expires_delta)


def create_refresh_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """创建 Refresh Token。

    Args:
        subject: Token 主体（通常是用户 ID）
        expires_delta: 自定义过期时间

    Returns:
        str: 编码后的 Refresh Token
    """
    return _create_token(subject, "refresh", expires_delta)
