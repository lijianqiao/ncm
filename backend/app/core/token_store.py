"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: token_store.py
@DateTime: 2026-01-07 00:00:00
@Docs: Refresh Token 存储与撤销（主流方案：Redis 优先，降级内存存储）

说明：
- 主要用于 Refresh Token 的“单端有效 + 轮换（rotation）+ 可撤销（revocation）”方案
- 优先使用 Redis 以支持多进程/多实例；若 Redis 不可用则降级为进程内内存存储（仅适合本地/测试）
"""

import asyncio
import time
from collections.abc import Iterable

from app.core import cache as cache_module
from app.core.config import settings
from app.core.logger import logger

_REVOKED_JTI = "__revoked__"
_REVOKED_AFTER_TTL_SECONDS = 30 * 24 * 3600  # 访问失效阈值的保存时长（30天），用于即时失效对比


def _default_ttl_seconds() -> int:
    """获取默认 TTL（秒）。

    Returns:
        int: TTL 秒数。
    """
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


class RefreshTokenStore:
    """Refresh Token 存储抽象基类。

    定义 Refresh Token 存储的接口，支持 Redis 和内存两种实现。
    """

    async def set_current_jti(self, user_id: str, jti: str, ttl_seconds: int) -> None:
        """设置当前用户的 JTI（JWT ID）。

        Args:
            user_id (str): 用户 ID。
            jti (str): JWT ID。
            ttl_seconds (int): 过期时间（秒）。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def get_current_jti(self, user_id: str) -> str | None:
        """获取当前用户的 JTI。

        Args:
            user_id (str): 用户 ID。

        Returns:
            str | None: JWT ID 或 None。
        """
        raise NotImplementedError

    async def revoke_user(self, user_id: str) -> None:
        """撤销用户的 Refresh Token。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def revoke_users(self, user_ids: Iterable[str]) -> None:
        """批量撤销用户的 Refresh Token。

        Args:
            user_ids (Iterable[str]): 用户 ID 列表。

        Returns:
            None: 无返回值。
        """
        for uid in user_ids:
            await self.revoke_user(uid)


def _refresh_key(user_id: str) -> str:
    """获取 Refresh Token 的 Redis Key。

    Args:
        user_id (str): 用户 ID。

    Returns:
        str: Redis Key。
    """
    return f"v1:auth:refresh:{user_id}"


class RedisRefreshTokenStore(RefreshTokenStore):
    """基于 Redis 的 Refresh Token 存储实现。"""

    async def set_current_jti(self, user_id: str, jti: str, ttl_seconds: int) -> None:
        """设置当前用户的 JTI（Redis 实现）。

        Args:
            user_id (str): 用户 ID。
            jti (str): JWT ID。
            ttl_seconds (int): 过期时间（秒）。

        Returns:
            None: 无返回值。
        """
        if cache_module.redis_client is None:
            return
        key = _refresh_key(user_id)
        try:
            await cache_module.redis_client.setex(key, ttl_seconds, jti)
        except Exception as e:
            logger.warning(f"refresh token 存储失败(REDIS): {e}")

    async def get_current_jti(self, user_id: str) -> str | None:
        """获取当前用户的 JTI（Redis 实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            str | None: JWT ID 或 None。
        """
        if cache_module.redis_client is None:
            return None
        key = _refresh_key(user_id)
        try:
            value = await cache_module.redis_client.get(key)
            if value:
                if isinstance(value, (bytes, bytearray)):
                    return value.decode("utf-8")
                return str(value)
        except Exception as e:
            logger.warning(f"refresh token 读取失败(REDIS): {e}")
        return None

    async def revoke_user(self, user_id: str) -> None:
        """撤销用户的 Refresh Token（Redis 实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        if cache_module.redis_client is None:
            return
        key = _refresh_key(user_id)
        try:
            await cache_module.redis_client.setex(key, _default_ttl_seconds(), _REVOKED_JTI)
        except Exception as e:
            logger.warning(f"refresh token 撤销失败(REDIS): {e}")


# ---- Access Token 即时失效阈值（revoked_after）----


def _revoked_after_key(user_id: str) -> str:
    """获取 Access Token 撤销时间戳的 Redis Key。

    Args:
        user_id (str): 用户 ID。

    Returns:
        str: Redis Key。
    """
    return f"v1:auth:revoked_after:{user_id}"


class AccessGate:
    """Access Token 即时失效门控抽象基类。

    用于实现 Access Token 的即时失效功能，通过记录撤销时间戳来判断 Token 是否有效。
    """

    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:  # pragma: no cover
        """设置用户的撤销时间戳。

        Args:
            user_id (str): 用户 ID。
            ts_seconds (float): 撤销时间戳（秒）。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def get_revoked_after(self, user_id: str) -> float | None:  # pragma: no cover
        """获取用户的撤销时间戳。

        Args:
            user_id (str): 用户 ID。

        Returns:
            float | None: 撤销时间戳或 None。
        """
        raise NotImplementedError

    async def revoke_now(self, user_id: str) -> None:  # pragma: no cover
        """立即撤销用户的 Access Token。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def revoke_many_now(self, user_ids: Iterable[str]) -> None:  # pragma: no cover
        """批量立即撤销用户的 Access Token。

        Args:
            user_ids (Iterable[str]): 用户 ID 列表。

        Returns:
            None: 无返回值。
        """
        for uid in user_ids:
            await self.revoke_now(uid)


class RedisAccessGate(AccessGate):
    """基于 Redis 的 Access Token 门控实现。"""

    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:
        """设置用户的撤销时间戳（Redis 实现）。

        Args:
            user_id (str): 用户 ID。
            ts_seconds (float): 撤销时间戳（秒）。

        Returns:
            None: 无返回值。
        """
        if cache_module.redis_client is None:
            return
        key = _revoked_after_key(user_id)
        try:
            await cache_module.redis_client.setex(key, _REVOKED_AFTER_TTL_SECONDS, str(int(ts_seconds)))
        except Exception as e:
            logger.warning(f"revoked_after 写入失败(REDIS): {e}")

    async def get_revoked_after(self, user_id: str) -> float | None:
        """获取用户的撤销时间戳（Redis 实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            float | None: 撤销时间戳或 None。
        """
        if cache_module.redis_client is None:
            return None
        key = _revoked_after_key(user_id)
        try:
            v = await cache_module.redis_client.get(key)
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
    """基于内存的 Access Token 门控实现（降级方案）。

    当 Redis 不可用时使用内存存储，数据仅在当前进程有效。
    """

    def __init__(self) -> None:
        """初始化内存 Access Gate。

        Returns:
            None: 无返回值。
        """
        self._lock = asyncio.Lock()
        # user_id -> (revoked_after_ts, expire_at)
        self._data: dict[str, tuple[float, float]] = {}

    async def set_revoked_after(self, user_id: str, ts_seconds: float) -> None:
        """设置用户的撤销时间戳（内存实现）。

        Args:
            user_id (str): 用户 ID。
            ts_seconds (float): 撤销时间戳（秒）。

        Returns:
            None: 无返回值。
        """
        expire_at = time.time() + _REVOKED_AFTER_TTL_SECONDS
        async with self._lock:
            self._data[user_id] = (float(ts_seconds), float(expire_at))

    async def get_revoked_after(self, user_id: str) -> float | None:
        """获取用户的撤销时间戳（内存实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            float | None: 撤销时间戳或 None（如果不存在或已过期）。
        """
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
    """进程内 Refresh Token 存储（仅用于本地/测试降级）"""

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
    # Redis 可用时优先；否则降级内存存储
    return _redis_store if cache_module.redis_client is not None else _memory_store


def get_access_gate() -> AccessGate:
    return _redis_gate if cache_module.redis_client is not None else _memory_gate


async def set_user_refresh_jti(*, user_id: str, jti: str, ttl_seconds: int) -> None:
    await get_refresh_token_store().set_current_jti(user_id, jti, ttl_seconds)


async def get_user_refresh_jti(*, user_id: str) -> str | None:
    return await get_refresh_token_store().get_current_jti(user_id)


async def revoke_user_refresh(*, user_id: str) -> None:
    await get_refresh_token_store().revoke_user(user_id)


async def revoke_users_refresh(*, user_ids: Iterable[str]) -> None:
    await get_refresh_token_store().revoke_users(user_ids)


# ---- 外部使用 Access Gate 方法 ----


async def set_user_revoked_after(*, user_id: str, ts_seconds: float) -> None:
    await get_access_gate().set_revoked_after(user_id, ts_seconds)


async def get_user_revoked_after(*, user_id: str) -> float | None:
    return await get_access_gate().get_revoked_after(user_id)


async def revoke_user_access_now(*, user_id: str) -> None:
    await get_access_gate().revoke_now(user_id)


async def revoke_users_access_now(*, user_ids: Iterable[str]) -> None:
    await get_access_gate().revoke_many_now(user_ids)
