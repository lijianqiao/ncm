"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_auth_service_refresh_extra.py
@DateTime: 2026-01-05 00:00:00
@Docs: AuthService.refresh_token 额外异常分支覆盖测试.
"""

import uuid
from typing import Any, cast

import pytest

from app.core.exceptions import UnauthorizedException
from app.services.auth_service import AuthService


class DummyCRUDUser:
    def __init__(self, user: object | None = None) -> None:
        self._user = user

    async def get(self, db, id):
        return self._user


class DummyUser:
    def __init__(self, user_id: uuid.UUID, *, is_active: bool = True) -> None:
        self.id = user_id
        self.is_active = is_active


def _make_auth_service(user: object | None = None) -> AuthService:
    return AuthService(
        db=cast(Any, object()),
        log_service=cast(Any, object()),
        user_crud=cast(Any, DummyCRUDUser(user)),
    )


@pytest.mark.asyncio
async def test_refresh_token_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    monkeypatch.setattr(
        mod.jwt,
        "decode",
        lambda *args, **kwargs: {"type": "access", "sub": str(uuid.uuid4()), "iss": "admin-rbac-backend", "jti": "x"},
    )

    svc = _make_auth_service()

    with pytest.raises(UnauthorizedException) as exc:
        await svc.refresh_token("x")

    assert exc.value.message == "无效的刷新令牌"


@pytest.mark.asyncio
async def test_refresh_token_missing_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    monkeypatch.setattr(
        mod.jwt, "decode", lambda *args, **kwargs: {"type": "refresh", "iss": "admin-rbac-backend", "jti": "x"}
    )

    svc = _make_auth_service()

    with pytest.raises(UnauthorizedException) as exc:
        await svc.refresh_token("x")

    assert exc.value.message == "无效的刷新令牌"


@pytest.mark.asyncio
async def test_refresh_token_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    class DummyInvalid(Exception):
        pass

    def raise_invalid(*args, **kwargs):
        raise DummyInvalid("bad")

    monkeypatch.setattr(mod, "InvalidTokenError", DummyInvalid)
    monkeypatch.setattr(mod.jwt, "decode", raise_invalid)

    svc = _make_auth_service()

    with pytest.raises(UnauthorizedException) as exc:
        await svc.refresh_token("x")

    assert exc.value.message == "无效的刷新令牌"


@pytest.mark.asyncio
async def test_refresh_token_invalid_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    monkeypatch.setattr(
        mod.jwt,
        "decode",
        lambda *args, **kwargs: {"type": "refresh", "sub": "not-uuid", "iss": "admin-rbac-backend", "jti": "x"},
    )

    svc = _make_auth_service()

    with pytest.raises(UnauthorizedException) as exc:
        await svc.refresh_token("x")

    assert "用户ID格式错误" in exc.value.message


@pytest.mark.asyncio
async def test_refresh_token_user_missing_or_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    uid = uuid.uuid4()
    monkeypatch.setattr(
        mod.jwt,
        "decode",
        lambda *args, **kwargs: {"type": "refresh", "sub": str(uid), "iss": "admin-rbac-backend", "jti": "x"},
    )

    # 用户不存在
    svc = _make_auth_service(None)
    with pytest.raises(UnauthorizedException) as exc1:
        await svc.refresh_token("x")
    assert "用户不存在或已禁用" in exc1.value.message

    # 用户被禁用
    svc2 = _make_auth_service(DummyUser(uid, is_active=False))
    with pytest.raises(UnauthorizedException) as exc2:
        await svc2.refresh_token("x")
    assert "用户不存在或已禁用" in exc2.value.message


@pytest.mark.asyncio
async def test_refresh_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_service as mod

    uid = uuid.uuid4()
    # 第一次 decode 用于校验传入 refresh；第二次 decode 用于解析新签发的 refresh
    decoded_payloads = [
        {"type": "refresh", "sub": str(uid), "iss": "admin-rbac-backend", "jti": "old"},
        {"type": "refresh", "sub": str(uid), "iss": "admin-rbac-backend", "jti": "new"},
    ]

    def _decode(*args, **kwargs):
        return decoded_payloads.pop(0)

    monkeypatch.setattr(mod.jwt, "decode", _decode)
    monkeypatch.setattr(mod.security, "create_access_token", lambda *args, **kwargs: "new_access")
    monkeypatch.setattr(mod.security, "create_refresh_token", lambda *args, **kwargs: "new_refresh")

    # 让 store 校验通过（模拟“当前 refresh jti == old”）
    async def _get_user_refresh_jti(*args, **kwargs):
        return "old"

    async def _set_user_refresh_jti(*args, **kwargs):
        return None

    monkeypatch.setattr(mod, "get_user_refresh_jti", _get_user_refresh_jti)
    monkeypatch.setattr(mod, "set_user_refresh_jti", _set_user_refresh_jti)

    svc = _make_auth_service(DummyUser(uid, is_active=True))
    token = await svc.refresh_token("refresh_x")

    assert token.access_token == "new_access"
    assert token.refresh_token == "new_refresh"
    assert token.token_type == "bearer"
