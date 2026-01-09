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
    return secrets.token_urlsafe(32)


def _refresh_cookie_path() -> str:
    # refresh_token 不需要被前端读取，尽量缩小发送范围
    return f"{settings.API_V1_STR}/auth"


def _csrf_cookie_path() -> str:
    # csrf_token 需要被前端在任意页面读取并回传请求头，因此必须放宽到 /
    return "/"


def refresh_cookie_name() -> str:
    return getattr(settings, "AUTH_REFRESH_COOKIE_NAME", "refresh_token")


def csrf_cookie_name() -> str:
    return getattr(settings, "AUTH_CSRF_COOKIE_NAME", "csrf_token")


def csrf_header_name() -> str:
    return getattr(settings, "AUTH_CSRF_HEADER_NAME", "X-CSRF-Token")


def cookie_domain() -> str | None:
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
    return bool(getattr(settings, "AUTH_COOKIE_SECURE", settings.ENVIRONMENT != "local"))


def cookie_samesite() -> Literal["lax", "strict", "none"]:
    v = str(getattr(settings, "AUTH_COOKIE_SAMESITE", "lax")).lower().strip()
    if v not in ("lax", "strict", "none"):
        return "lax"
    return v  # type: ignore[return-value]


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
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
    # delete_cookie 默认会把值清掉；path/domain 必须与 set_cookie 一致
    response.delete_cookie(key=refresh_cookie_name(), path=_refresh_cookie_path(), domain=cookie_domain())
    response.delete_cookie(key=csrf_cookie_name(), path=_csrf_cookie_path(), domain=cookie_domain())
