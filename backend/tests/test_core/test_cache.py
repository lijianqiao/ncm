"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_cache.py
@DateTime: 2026-01-05 00:00:00
@Docs: 缓存模块单元测试.
"""

import fnmatch
import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest

from app.core import cache as cache_module


class FakeRedis:
    """用于测试的简易异步 Redis 客户端."""

    def __init__(
        self,
        initial: dict[str, str] | None = None,
        *,
        raise_on_get: bool = False,
        raise_on_setex: bool = False,
        raise_on_scan: bool = False,
    ) -> None:
        self.store: dict[str, str] = dict(initial or {})
        self.raise_on_get = raise_on_get
        self.raise_on_setex = raise_on_setex
        self.raise_on_scan = raise_on_scan
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        if self.raise_on_get:
            raise RuntimeError("boom")
        return self.store.get(key)

    async def setex(self, key: str, expire: int, value: str) -> None:
        if self.raise_on_setex:
            raise RuntimeError("boom")
        self.store[key] = value

    async def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        self.deleted.append(key)
        return 1 if existed else 0

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        if self.raise_on_scan:
            raise RuntimeError("boom")
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key


@pytest.mark.asyncio
async def test_cache_decorator_disabled_executes_original(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module, "redis_client", None)

    called = {"count": 0}

    @cache_module.cache(prefix="v1:test", expire=10)
    async def func(x: int) -> dict[str, int]:
        called["count"] += 1
        return {"x": x}

    assert await func(1) == {"x": 1}
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_cache_decorator_cache_hit_skips_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(cache_module, "redis_client", fake)

    class Svc:
        def __init__(self) -> None:
            self.called = 0

        @cache_module.cache(prefix="v1:test", expire=10)
        async def calc(self, x: int) -> dict[str, int]:
            self.called += 1
            return {"x": x}

    svc = Svc()

    # 预先写入缓存（覆盖 self 参数排除分支）
    cache_key = cache_module._generate_cache_key("v1:test", Svc.calc.__wrapped__, (svc, 2), {})  # type: ignore[attr-defined]
    fake.store[cache_key] = json.dumps({"x": 999})

    assert await svc.calc(2) == {"x": 999}
    assert svc.called == 0


@pytest.mark.asyncio
async def test_cache_decorator_cache_miss_then_write(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(cache_module, "redis_client", fake)

    @cache_module.cache(prefix="v1:test", expire=10)
    async def func(x: int) -> dict[str, int]:
        return {"x": x}

    result = await func(3)
    assert result == {"x": 3}

    # 至少写入了一个 key
    assert len(fake.store) == 1


@pytest.mark.asyncio
async def test_cache_decorator_read_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(raise_on_get=True)
    monkeypatch.setattr(cache_module, "redis_client", fake)

    @cache_module.cache(prefix="v1:test", expire=10)
    async def func(x: int) -> dict[str, int]:
        return {"x": x}

    assert await func(4) == {"x": 4}


@pytest.mark.asyncio
async def test_invalidate_cache_disabled_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module, "redis_client", None)
    assert await cache_module.invalidate_cache("v1:menu:*") == 0


@pytest.mark.asyncio
async def test_invalidate_cache_deletes_matching_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(
        {
            "v1:menu:a": "1",
            "v1:menu:b": "2",
            "v1:user:c": "3",
        }
    )
    monkeypatch.setattr(cache_module, "redis_client", fake)

    deleted = await cache_module.invalidate_cache("v1:menu:*")
    assert deleted == 2
    assert "v1:user:c" in fake.store


@pytest.mark.asyncio
async def test_invalidate_cache_scan_error_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis({"v1:menu:a": "1"}, raise_on_scan=True)
    monkeypatch.setattr(cache_module, "redis_client", fake)

    deleted = await cache_module.invalidate_cache("v1:menu:*")
    assert deleted == 0


def test_user_permissions_cache_key() -> None:
    uid = uuid4()
    assert cache_module.user_permissions_cache_key(uid) == f"v1:user:permissions:{uid}"


@pytest.mark.asyncio
async def test_invalidate_user_permissions_cache_early_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module, "redis_client", None)
    assert await cache_module.invalidate_user_permissions_cache([uuid4()]) == 0

    fake = FakeRedis()
    monkeypatch.setattr(cache_module, "redis_client", fake)
    assert await cache_module.invalidate_user_permissions_cache([]) == 0


@pytest.mark.asyncio
async def test_invalidate_user_permissions_cache_deletes_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    uid1 = uuid4()
    uid2 = uuid4()

    fake = FakeRedis(
        {
            cache_module.user_permissions_cache_key(uid1): "1",
            cache_module.user_permissions_cache_key(uid2): "2",
        }
    )
    monkeypatch.setattr(cache_module, "redis_client", fake)

    deleted = await cache_module.invalidate_user_permissions_cache([uid1, uid2])
    assert deleted == 2
    assert cache_module.user_permissions_cache_key(uid1) in fake.deleted


@pytest.mark.asyncio
async def test_invalidate_user_permissions_cache_delete_error_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenRedis(FakeRedis):
        async def delete(self, key: str) -> int:  # type: ignore[override]
            raise RuntimeError("boom")

    uid = UUID("00000000-0000-0000-0000-000000000001")
    fake = BrokenRedis({cache_module.user_permissions_cache_key(uid): "1"})
    monkeypatch.setattr(cache_module, "redis_client", fake)

    deleted = await cache_module.invalidate_user_permissions_cache([uid])
    assert deleted == 0
