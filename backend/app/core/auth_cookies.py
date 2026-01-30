"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: auth_cookies.py
@DateTime: 2026-01-08 00:00:00
@Docs: 认证 Cookie 工具（Refresh Token + CSRF）。

约定：
- Refresh Token 放 HttpOnly Cookie。
- CSRF Token 放非 HttpOnly Cookie，前端读取后在请求头 X-CSRF-Token 回传。
"""

import secrets
from typing import Literal

from fastapi import Response

from app.core.config import settings


def generate_csrf_token() -> str:
    """生成 CSRF Token。

    Returns:
        str: URL 安全的随机 Token 字符串。
    """
    return secrets.token_urlsafe(32)


def _refresh_cookie_path() -> str:
    """获取 Refresh Token Cookie 路径。

    refresh_token 不需要被前端读取，尽量缩小发送范围。

    Returns:
        str: Cookie 路径。
    """
    return f"{settings.API_V1_STR}/auth"


def _csrf_cookie_path() -> str:
    """获取 CSRF Token Cookie 路径。

    csrf_token 需要被前端在任意页面读取并回传请求头，因此必须放宽到 /。

    Returns:
        str: Cookie 路径。
    """
    return "/"


def refresh_cookie_name() -> str:
    """获取 Refresh Token Cookie 名称。

    Returns:
        str: Cookie 名称。
    """
    return getattr(settings, "AUTH_REFRESH_COOKIE_NAME", "refresh_token")


def csrf_cookie_name() -> str:
    """获取 CSRF Token Cookie 名称。

    Returns:
        str: Cookie 名称。
    """
    return getattr(settings, "AUTH_CSRF_COOKIE_NAME", "csrf_token")


def csrf_header_name() -> str:
    """获取 CSRF Token HTTP 请求头名称。

    Returns:
        str: 请求头名称。
    """
    return getattr(settings, "AUTH_CSRF_HEADER_NAME", "X-CSRF-Token")


def cookie_domain() -> str | None:
    """获取 Cookie 域名。

    Returns:
        str | None: Cookie 域名，如果未配置则返回 None。
    """
    v = getattr(settings, "AUTH_COOKIE_DOMAIN", None)
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.lower() in ("none", "null"):
        return None
    return s


def cookie_secure() -> bool:
    """获取 Cookie Secure 标志。

    Returns:
        bool: 如果应使用 Secure 标志则返回 True。
    """
    return bool(getattr(settings, "AUTH_COOKIE_SECURE", settings.ENVIRONMENT != "local"))


def cookie_samesite() -> Literal["lax", "strict", "none"]:
    """获取 Cookie SameSite 设置。

    Returns:
        Literal["lax", "strict", "none"]: SameSite 值。
    """
    v = str(getattr(settings, "AUTH_COOKIE_SAMESITE", "lax")).lower().strip()
    if v not in ("lax", "strict", "none"):
        return "lax"
    return v  # type: ignore[return-value]


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """设置 Refresh Token Cookie。

    Args:
        response (Response): FastAPI 响应对象。
        refresh_token (str): Refresh Token 字符串。

    Returns:
        None: 无返回值。
    """
    response.set_cookie(
        key=refresh_cookie_name(),
        value=refresh_token,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        path=_refresh_cookie_path(),
        domain=cookie_domain(),
        max_age=int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """设置 CSRF Token Cookie。

    Args:
        response (Response): FastAPI 响应对象。
        csrf_token (str): CSRF Token 字符串。

    Returns:
        None: 无返回值。
    """
    response.set_cookie(
        key=csrf_cookie_name(),
        value=csrf_token,
        httponly=False,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        path=_csrf_cookie_path(),
        domain=cookie_domain(),
        max_age=int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )


def clear_auth_cookies(response: Response) -> None:
    """清除认证相关的 Cookie。

    delete_cookie 默认会把值清掉；path/domain 必须与 set_cookie 一致。

    Args:
        response (Response): FastAPI 响应对象。

    Returns:
        None: 无返回值。
    """
    response.delete_cookie(key=refresh_cookie_name(), path=_refresh_cookie_path(), domain=cookie_domain())
    response.delete_cookie(key=csrf_cookie_name(), path=_csrf_cookie_path(), domain=cookie_domain())
