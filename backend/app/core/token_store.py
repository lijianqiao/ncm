"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: token_store.py
@DateTime: 2026-01-07 00:00:00
@Docs: Refresh Token 存储与撤销（主流方案：Redis 优先，降级内存存储）。

说明：
- 主要用于 Refresh Token 的“单端有效 + 轮换（rotation）+ 可撤销（revocation）”。
- 优先使用 Redis 以支持多进程/多实例；若 Redis 不可用则降级为进程内内存存储（仅适合本地/测试）。
"""

import asyncio
import time
from collections.abc import Iterable

from app.core.cache import redis_client
from app.core.config import settings
from app.core.logger import logger

_REVOKED_JTI = "__revoked__"
_REVOKED_AFTER_TTL_SECONDS = 30 * 24 * 3600  # 访问失效阈值的保存时长（30天），用于即时失效对比


def _default_ttl_seconds() -> int:
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


class RefreshTokenStore:
    async def set_current_jti(self, user_id: str, jti: str, ttl_seconds: int) -> None:
        raise NotImplementedError

    async def get_current_jti(self, user_id: str) -> str | None:
        raise NotImplementedError

    async def revoke_user(self, user_id: str) -> None:
        raise NotImplementedError

    async def revoke_users(self, user_ids: Iterable[str]) -> None:
        for uid in user_ids:
            await self.revoke_user(uid)


def _refresh_key(user_id: str) -> str:
    return f"v1:auth:refresh:{user_id}"


class RedisRefreshTokenStore(RefreshTokenStore):
    async def set_current_jti(self, user_id: str, jti: str, ttl_seconds: int) -> None:
        if redis_client is None:
            return
        key = _refresh_key(user_id)
        try:
            await redis_client.setex(key, ttl_seconds, jti)
        except Exception as e:
            logger.warning(f"refresh token 存储失败(REDIS): {e}")

    async def get_current_jti(self, user_id: str) -> str | None:
        if redis_client is None:
            return None
        key = _refresh_key(user_id)
        try:
            value = await redis_client.get(key)
            if value:
                if isinstance(value, (bytes, bytearray)):
                    return value.decode("utf-8")
                return str(value)
        except Exception as e:
            logger.warning(f"refresh token 读取失败(REDIS): {e}")
        return None

    async def revoke_user(self, user_id: str) -> None:
        if redis_client is None:
            return
        key = _refresh_key(user_id)
        try:
            await redis_client.setex(key, _default_ttl_seconds(), _REVOKED_JTI)
        except Exception as e:
            logger.warning(f"refresh token 撤销失败(REDIS): {e}")


# ---- Access Token 即时失效阈值（revoked_after） ----


def _revoked_after_key(user_id: str) -> str:
    return f"v1:auth:revoked_after:{user_id}"


class AccessGate:
    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get_revoked_after(self, user_id: str) -> float | None:  # pragma: no cover
        raise NotImplementedError

    async def revoke_now(self, user_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def revoke_many_now(self, user_ids: Iterable[str]) -> None:  # pragma: no cover
        for uid in user_ids:
            await self.revoke_now(uid)


class RedisAccessGate(AccessGate):
    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:
        if redis_client is None:
            return
        key = _revoked_after_key(user_id)
        try:
            await redis_client.setex(key, _REVOKED_AFTER_TTL_SECONDS, str(int(ts_seconds)))
        except Exception as e:
            logger.warning(f"revoked_after 写入失败(REDIS): {e}")

    async def get_revoked_after(self, user_id: str) -> float | None:
        if redis_client is None:
            return None
        key = _revoked_after_key(user_id)
        try:
            v = await redis_client.get(key)
            if not v:
                return None
            try:
                return float(v)
            except Exception:
                return None
        except Exception as e:
            logger.warning(f"revoked_after 读取失败(REDIS): {e}")
            return None

    async def revoke_now(self, user_id: str) -> None:
        await self.set_revoked_after(user_id, time.time())


class MemoryAccessGate(AccessGate):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # user_id -> (revoked_after_ts, expire_at)
        self._data: dict[str, tuple[float, float]] = {}

    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:
        expire_at = time.time() + _REVOKED_AFTER_TTL_SECONDS
        async with self._lock:
            self._data[user_id] = (float(ts_seconds), float(expire_at))

    async def get_revoked_after(self, user_id: str) -> float | None:
        now = time.time()
        async with self._lock:
            v = self._data.get(user_id)
            if not v:
                return None
            ts, exp = v
            if exp <= now:
                self._data.pop(user_id, None)
                return None
            return float(ts)

    async def revoke_now(self, user_id: str) -> None:
        await self.set_revoked_after(user_id, time.time())


class MemoryRefreshTokenStore(RefreshTokenStore):
    """进程内 Refresh Token 存储（仅用于本地/测试降级）。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # user_id -> (jti, expire_at)
        self._data: dict[str, tuple[str, float]] = {}

    async def set_current_jti(self, user_id: str, jti: str, ttl_seconds: int) -> None:
        expire_at = time.time() + max(1, int(ttl_seconds))
        async with self._lock:
            self._data[user_id] = (jti, expire_at)

    async def get_current_jti(self, user_id: str) -> str | None:
        now = time.time()
        async with self._lock:
            value = self._data.get(user_id)
            if not value:
                return None
            jti, expire_at = value
            if expire_at <= now:
                self._data.pop(user_id, None)
                return None
            return jti

    async def revoke_user(self, user_id: str) -> None:
        expire_at = time.time() + max(1, _default_ttl_seconds())
        async with self._lock:
            self._data[user_id] = (_REVOKED_JTI, expire_at)


_memory_store = MemoryRefreshTokenStore()
_redis_store = RedisRefreshTokenStore()
_memory_gate = MemoryAccessGate()
_redis_gate = RedisAccessGate()


def get_refresh_token_store() -> RefreshTokenStore:
    # Redis 可用时优先；否则降级内存。
    return _redis_store if redis_client is not None else _memory_store


def get_access_gate() -> AccessGate:
    return _redis_gate if redis_client is not None else _memory_gate


async def set_user_refresh_jti(*, user_id: str, jti: str, ttl_seconds: int) -> None:
    await get_refresh_token_store().set_current_jti(user_id, jti, ttl_seconds)


async def get_user_refresh_jti(*, user_id: str) -> str | None:
    return await get_refresh_token_store().get_current_jti(user_id)


async def revoke_user_refresh(*, user_id: str) -> None:
    await get_refresh_token_store().revoke_user(user_id)


async def revoke_users_refresh(*, user_ids: Iterable[str]) -> None:
    await get_refresh_token_store().revoke_users(user_ids)


# ---- 外部使用的 Access Gate 方法 ----


async def set_user_revoked_after(*, user_id: str, ts_seconds: float) -> None:
    await get_access_gate().set_revoked_after(user_id, ts_seconds)


async def get_user_revoked_after(*, user_id: str) -> float | None:
    return await get_access_gate().get_revoked_after(user_id)


async def revoke_user_access_now(*, user_id: str) -> None:
    await get_access_gate().revoke_now(user_id)


async def revoke_users_access_now(*, user_ids: Iterable[str]) -> None:
    await get_access_gate().revoke_many_now(user_ids)
