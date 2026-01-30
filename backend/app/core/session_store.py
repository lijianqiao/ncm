"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: session_store.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话存储（Redis 优先，降级内存）

说明：
- 用于“在线用户列表/ 最后活跃时间/ 强制下线”等功能
- 以 refresh 会话为主：登录时刷新（touch）；注销/强制下线时删除（remove）
"""

import asyncio
import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from app.core import cache as cache_module
from app.core.config import settings
from app.core.logger import logger


@dataclass(frozen=True, slots=True)
class OnlineSession:
    """在线会话信息。

    Attributes:
        user_id (str): 用户 ID。
        username (str): 用户名。
        ip (str | None): 客户端 IP 地址。
        user_agent (str | None): 用户代理字符串。
        login_at (float): 登录时间戳。
        last_seen_at (float): 最后活跃时间戳。
    """

    user_id: str
    username: str
    ip: str | None
    user_agent: str | None
    login_at: float
    last_seen_at: float


def _online_zset_key() -> str:
    """获取在线用户有序集合的 Redis Key。

    Returns:
        str: Redis Key。
    """
    return "v1:auth:online:zset"


def _session_key(user_id: str) -> str:
    """获取用户会话的 Redis Key。

    Args:
        user_id (str): 用户 ID。

    Returns:
        str: Redis Key。
    """
    return f"v1:auth:session:{user_id}"


def _default_online_ttl_seconds() -> int:
    """获取默认在线会话 TTL（秒）。

    Returns:
        int: TTL 秒数。
    """
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


class SessionStore:
    """会话存储抽象基类。

    定义在线会话存储的接口，支持 Redis 和内存两种实现。
    """

    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        """更新或插入会话。

        Args:
            session (OnlineSession): 会话对象。
            ttl_seconds (int): 过期时间（秒）。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def get_session(self, user_id: str) -> OnlineSession | None:
        """获取会话。

        Args:
            user_id (str): 用户 ID。

        Returns:
            OnlineSession | None: 会话对象或 None。
        """
        raise NotImplementedError

    async def remove_session(self, user_id: str) -> None:
        """删除会话。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        raise NotImplementedError

    async def list_online(
        self, *, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OnlineSession], int]:
        """分页列出在线用户。

        Args:
            page (int): 页码。
            page_size (int): 每页数量。
            keyword (str | None): 搜索关键词，默认为 None。

        Returns:
            tuple[list[OnlineSession], int]: 在线会话列表和总数。
        """
        raise NotImplementedError

    async def remove_sessions(self, user_ids: Iterable[str]) -> None:
        """批量删除会话。

        Args:
            user_ids (Iterable[str]): 用户 ID 列表。

        Returns:
            None: 无返回值。
        """
        for uid in user_ids:
            await self.remove_session(uid)


class RedisSessionStore(SessionStore):
    """基于 Redis 的会话存储实现。

    使用 Redis 有序集合（ZSET）存储在线用户列表，使用普通 Key 存储会话详情。
    """

    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        """更新或插入会话（Redis 实现）。

        Args:
            session (OnlineSession): 会话对象。
            ttl_seconds (int): 过期时间（秒）。

        Returns:
            None: 无返回值。
        """
        if cache_module.redis_client is None:
            return

        now = time.time()
        zkey = _online_zset_key()
        skey = _session_key(session.user_id)

        try:
            await cache_module.redis_client.zadd(zkey, {session.user_id: float(session.last_seen_at)})
            await cache_module.redis_client.setex(
                skey, max(1, int(ttl_seconds)), json.dumps(asdict(session), ensure_ascii=False)
            )
            # 在线 zset 本身设置一个 TTL，避免长期无人用时残留
            await cache_module.redis_client.expire(zkey, max(60, int(_default_online_ttl_seconds())))
        except Exception as e:
            logger.warning(f"在线会话写入失败(REDIS): {e}")

        # 轻量清理：移除过期成员（last_seen 太久远未更新的）
        try:
            cutoff = now - max(60, int(ttl_seconds))
            await cache_module.redis_client.zremrangebyscore(zkey, 0, cutoff)
        except Exception:
            pass

    async def get_session(self, user_id: str) -> OnlineSession | None:
        """获取会话（Redis 实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            OnlineSession | None: 会话对象或 None。
        """
        if cache_module.redis_client is None:
            return None

        skey = _session_key(user_id)
        try:
            raw = await cache_module.redis_client.get(skey)
            if not raw:
                return None
            data = json.loads(raw)
            return OnlineSession(
                user_id=str(data.get("user_id")),
                username=str(data.get("username")),
                ip=data.get("ip"),
                user_agent=data.get("user_agent"),
                login_at=float(data.get("login_at")),
                last_seen_at=float(data.get("last_seen_at")),
            )
        except Exception as e:
            logger.warning(f"在线会话读取失败(REDIS): {e}")
            return None

    async def remove_session(self, user_id: str) -> None:
        """删除会话（Redis 实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        if cache_module.redis_client is None:
            return

        zkey = _online_zset_key()
        skey = _session_key(user_id)
        try:
            await cache_module.redis_client.zrem(zkey, user_id)
            await cache_module.redis_client.delete(skey)
        except Exception as e:
            logger.warning(f"在线会话删除失败(REDIS): {e}")

    async def remove_user_sessions_by_user_id(self, user_id: str) -> None:
        """按 user_id 删除该用户的所有在线会话记录（兼容历史数据）。

        说明：
        - 当前实现是 user_id 作为 zset member
        - 历史版本可能把“session_id”写入 zset member，导致同一用户出现多条会话
        - 这里通过扫描 zset 并读取 session 内容来定位并清理所有属于该用户的成员
        """

        if cache_module.redis_client is None:
            return

        zkey = _online_zset_key()
        target_uid = str(user_id)

        # 先删除当前规范key（幂等）
        try:
            await cache_module.redis_client.zrem(zkey, target_uid)
            await cache_module.redis_client.delete(_session_key(target_uid))
        except Exception:
            pass

        cursor = 0
        try:
            while True:
                cursor, pairs = await cache_module.redis_client.zscan(zkey, cursor=cursor, count=200)
                for member, _score in pairs:
                    mid = str(member)

                    # member 本身就是 user_id 的情况（兜底处理）
                    if mid == target_uid:
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                            await cache_module.redis_client.delete(_session_key(mid))
                        except Exception:
                            pass
                        continue

                    session = await self.get_session(mid)
                    if session is None:
                        # 无效成员：顺手清理
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                        except Exception:
                            pass
                        continue

                    if str(session.user_id) == target_uid:
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                            await cache_module.redis_client.delete(_session_key(mid))
                            await cache_module.redis_client.delete(_session_key(target_uid))
                        except Exception:
                            pass

                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"在线会话按用户清理失效REDIS): {e}")

    async def remove_user_sessions_many_by_user_ids(self, user_ids: Iterable[str]) -> None:
        """批量按 user_id 删除会话（兼容历史数据）。

        Args:
            user_ids (Iterable[str]): 用户 ID 列表。

        Returns:
            None: 无返回值。
        """

        if cache_module.redis_client is None:
            return

        targets = {str(x) for x in user_ids if str(x).strip()}
        if not targets:
            return

        zkey = _online_zset_key()

        # 先删除规范key（幂等）
        try:
            for uid in targets:
                await cache_module.redis_client.zrem(zkey, uid)
                await cache_module.redis_client.delete(_session_key(uid))
        except Exception:
            pass

        cursor = 0
        try:
            while True:
                cursor, pairs = await cache_module.redis_client.zscan(zkey, cursor=cursor, count=200)
                for member, _score in pairs:
                    mid = str(member)

                    if mid in targets:
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                            await cache_module.redis_client.delete(_session_key(mid))
                        except Exception:
                            pass
                        continue

                    session = await self.get_session(mid)
                    if session is None:
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                        except Exception:
                            pass
                        continue

                    if str(session.user_id) in targets:
                        try:
                            await cache_module.redis_client.zrem(zkey, mid)
                            await cache_module.redis_client.delete(_session_key(mid))
                            await cache_module.redis_client.delete(_session_key(str(session.user_id)))
                        except Exception:
                            pass

                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"在线会话批量按用户清理失效REDIS): {e}")

    async def list_online(
        self, *, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OnlineSession], int]:
        """分页列出在线用户（Redis 实现）。

        Args:
            page (int): 页码。
            page_size (int): 每页数量。
            keyword (str | None): 搜索关键词（支持用户名和 IP），默认为 None。

        Returns:
            tuple[list[OnlineSession], int]: 在线会话列表和总数。
        """
        if cache_module.redis_client is None:
            return [], 0

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        zkey = _online_zset_key()

        # 使用游标分页扫描，限制最大扫描数量避免阻塞 Redis
        MAX_SCAN_ITERATIONS = 50  # 最大扫描迭代次数
        SCAN_BATCH_SIZE = 200  # 每次扫描数量

        sessions_by_user: dict[str, OnlineSession] = {}
        cursor = 0
        iterations = 0
        cleanup_tasks: list[str] = []  # 收集需要清理的成员，批量处理

        try:
            while iterations < MAX_SCAN_ITERATIONS:
                iterations += 1
                cursor, pairs = await cache_module.redis_client.zscan(
                    zkey, cursor=cursor, count=SCAN_BATCH_SIZE
                )

                for member, _score in pairs:
                    mid = str(member)
                    session = await self.get_session(mid)

                    if session is None:
                        # member 对应的 session key 已过期不存在：标记清理
                        cleanup_tasks.append(mid)
                        continue

                    # 兼容历史数据：member 可能不是 user_id（例：session_id）
                    if mid != str(session.user_id):
                        try:
                            # 迁移为规范 member=user_id
                            await cache_module.redis_client.zadd(
                                zkey, {str(session.user_id): float(session.last_seen_at)}
                            )
                            await cache_module.redis_client.setex(
                                _session_key(str(session.user_id)),
                                max(1, int(_default_online_ttl_seconds())),
                                json.dumps(asdict(session), ensure_ascii=False),
                            )
                            cleanup_tasks.append(mid)
                        except Exception:
                            pass

                    uid = str(session.user_id)
                    existing = sessions_by_user.get(uid)
                    if existing is None or float(session.last_seen_at) > float(existing.last_seen_at):
                        sessions_by_user[uid] = session

                if cursor == 0:
                    break

            # 批量清理无效成员（使用 Pipeline 减少网络往返）
            if cleanup_tasks:
                try:
                    async with cache_module.redis_client.pipeline() as pipe:
                        for mid in cleanup_tasks:
                            pipe.zrem(zkey, mid)
                            pipe.delete(_session_key(mid))
                        await pipe.execute()
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"在线会话列表扫描失败(REDIS): {e}")
            return [], 0

        sessions: list[OnlineSession] = list(sessions_by_user.values())

        # 关键词过滤：支持用户名和 IP 搜索
        if keyword:
            kw = keyword.strip().lower()
            if kw:
                sessions = [s for s in sessions if kw in (s.username or "").lower() or kw in (s.ip or "").lower()]

        sessions.sort(key=lambda x: float(x.last_seen_at), reverse=True)
        total = len(sessions)

        start = (page - 1) * page_size
        end = start + page_size
        return sessions[start:end], total


class MemorySessionStore(SessionStore):
    """基于内存的会话存储实现（降级方案）。

    当 Redis 不可用时使用内存存储，数据仅在当前进程有效。
    """

    def __init__(self) -> None:
        """初始化内存会话存储。

        Returns:
            None: 无返回值。
        """
        self._lock = asyncio.Lock()
        # user_id -> (session, expire_at)
        self._data: dict[str, tuple[OnlineSession, float]] = {}

    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        """更新或插入会话（内存实现）。

        Args:
            session (OnlineSession): 会话对象。
            ttl_seconds (int): 过期时间（秒）。

        Returns:
            None: 无返回值。
        """
        expire_at = time.time() + max(1, int(ttl_seconds))
        async with self._lock:
            self._data[session.user_id] = (session, expire_at)

    async def get_session(self, user_id: str) -> OnlineSession | None:
        """获取会话（内存实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            OnlineSession | None: 会话对象或 None（如果不存在或已过期）。
        """
        now = time.time()
        async with self._lock:
            value = self._data.get(user_id)
            if not value:
                return None
            session, expire_at = value
            if expire_at <= now:
                self._data.pop(user_id, None)
                return None
            return session

    async def remove_session(self, user_id: str) -> None:
        """删除会话（内存实现）。

        Args:
            user_id (str): 用户 ID。

        Returns:
            None: 无返回值。
        """
        async with self._lock:
            self._data.pop(user_id, None)

    async def list_online(
        self, *, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OnlineSession], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        now = time.time()
        async with self._lock:
            # 清理过期
            expired = [uid for uid, (_, exp) in self._data.items() if exp <= now]
            for uid in expired:
                self._data.pop(uid, None)

            items = [s for (s, _) in self._data.values()]

        items.sort(key=lambda x: x.last_seen_at, reverse=True)

        # 关键词过滤：支持用户名和 IP 搜索
        if keyword:
            kw = keyword.strip().lower()
            if kw:
                items = [s for s in items if kw in (s.username or "").lower() or kw in (s.ip or "").lower()]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total


_memory_store = MemorySessionStore()
_redis_store = RedisSessionStore()


def get_session_store() -> SessionStore:
    return _redis_store if cache_module.redis_client is not None else _memory_store


async def touch_online_session(
    *,
    user_id: str,
    username: str,
    ip: str | None,
    user_agent: str | None,
    ttl_seconds: int | None = None,
    login_at: float | None = None,
) -> None:
    now = time.time()
    ttl = _default_online_ttl_seconds() if ttl_seconds is None else int(ttl_seconds)

    existing = await get_session_store().get_session(user_id)
    session = OnlineSession(
        user_id=user_id,
        username=username,
        ip=ip,
        user_agent=user_agent,
        login_at=float(login_at if login_at is not None else (existing.login_at if existing else now)),
        last_seen_at=now,
    )
    await get_session_store().upsert_session(session, ttl_seconds=ttl)


async def remove_online_session(*, user_id: str) -> None:
    store = get_session_store()
    if isinstance(store, RedisSessionStore):
        await store.remove_user_sessions_by_user_id(user_id)
        return
    await store.remove_session(user_id)


async def remove_online_sessions(*, user_ids: Iterable[str]) -> None:
    store = get_session_store()
    if isinstance(store, RedisSessionStore):
        await store.remove_user_sessions_many_by_user_ids(user_ids)
        return
    await store.remove_sessions(user_ids)


async def list_online_sessions(
    *, page: int = 1, page_size: int = 20, keyword: str | None = None
) -> tuple[list[OnlineSession], int]:
    return await get_session_store().list_online(page=page, page_size=page_size, keyword=keyword)
