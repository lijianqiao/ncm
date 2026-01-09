"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: session_store.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话存储（Redis 优先，降级内存）。

说明：
- 用于“在线用户列表 / 最后活跃时间 / 强制下线”。
- 以 refresh 会话为主：登录/刷新时 touch；注销/强制下线时 remove。
"""

import asyncio
import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from app.core.cache import redis_client
from app.core.config import settings
from app.core.logger import logger


@dataclass(frozen=True, slots=True)
class OnlineSession:
    user_id: str
    username: str
    ip: str | None
    user_agent: str | None
    login_at: float
    last_seen_at: float


def _online_zset_key() -> str:
    return "v1:auth:online:zset"


def _session_key(user_id: str) -> str:
    return f"v1:auth:session:{user_id}"


def _default_online_ttl_seconds() -> int:
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


class SessionStore:
    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        raise NotImplementedError

    async def get_session(self, user_id: str) -> OnlineSession | None:
        raise NotImplementedError

    async def remove_session(self, user_id: str) -> None:
        raise NotImplementedError

    async def list_online(
        self, *, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OnlineSession], int]:
        raise NotImplementedError

    async def remove_sessions(self, user_ids: Iterable[str]) -> None:
        for uid in user_ids:
            await self.remove_session(uid)


class RedisSessionStore(SessionStore):
    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        if redis_client is None:
            return

        now = time.time()
        zkey = _online_zset_key()
        skey = _session_key(session.user_id)

        try:
            await redis_client.zadd(zkey, {session.user_id: float(session.last_seen_at)})
            await redis_client.setex(skey, max(1, int(ttl_seconds)), json.dumps(asdict(session), ensure_ascii=False))
            # 在线 zset 本身设置一个 TTL，避免长期无人用时残留
            await redis_client.expire(zkey, max(60, int(_default_online_ttl_seconds())))
        except Exception as e:
            logger.warning(f"在线会话写入失败(REDIS): {e}")

        # 轻量清理：移除过期成员（last_seen 太久）
        try:
            cutoff = now - max(60, int(ttl_seconds))
            await redis_client.zremrangebyscore(zkey, 0, cutoff)
        except Exception:
            pass

    async def get_session(self, user_id: str) -> OnlineSession | None:
        if redis_client is None:
            return None

        skey = _session_key(user_id)
        try:
            raw = await redis_client.get(skey)
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
        if redis_client is None:
            return

        zkey = _online_zset_key()
        skey = _session_key(user_id)
        try:
            await redis_client.zrem(zkey, user_id)
            await redis_client.delete(skey)
        except Exception as e:
            logger.warning(f"在线会话删除失败(REDIS): {e}")

    async def remove_user_sessions_by_user_id(self, user_id: str) -> None:
        """按 user_id 删除该用户的所有在线会话记录（兼容历史数据）。

        说明：
        - 当前实现以 user_id 作为 zset member。
        - 历史版本可能把“session_id”写入 zset member，导致同一用户出现多条会话。
        - 这里通过扫描 zset 并读取 session 内容来定位并清理所有属于该用户的成员。
        """

        if redis_client is None:
            return

        zkey = _online_zset_key()
        target_uid = str(user_id)

        # 先删除当前规范 key（幂等）
        try:
            await redis_client.zrem(zkey, target_uid)
            await redis_client.delete(_session_key(target_uid))
        except Exception:
            pass

        cursor = 0
        try:
            while True:
                cursor, pairs = await redis_client.zscan(zkey, cursor=cursor, count=200)
                for member, _score in pairs:
                    mid = str(member)

                    # member 本身就是 user_id 的情况（兜底）
                    if mid == target_uid:
                        try:
                            await redis_client.zrem(zkey, mid)
                            await redis_client.delete(_session_key(mid))
                        except Exception:
                            pass
                        continue

                    session = await self.get_session(mid)
                    if session is None:
                        # 无效成员：顺手清理
                        try:
                            await redis_client.zrem(zkey, mid)
                        except Exception:
                            pass
                        continue

                    if str(session.user_id) == target_uid:
                        try:
                            await redis_client.zrem(zkey, mid)
                            await redis_client.delete(_session_key(mid))
                            await redis_client.delete(_session_key(target_uid))
                        except Exception:
                            pass

                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"在线会话按用户清理失败(REDIS): {e}")

    async def remove_user_sessions_many_by_user_ids(self, user_ids: Iterable[str]) -> None:
        """批量按 user_id 删除会话（兼容历史数据）。"""

        if redis_client is None:
            return

        targets = {str(x) for x in user_ids if str(x).strip()}
        if not targets:
            return

        zkey = _online_zset_key()

        # 先删除规范 key（幂等）
        try:
            for uid in targets:
                await redis_client.zrem(zkey, uid)
                await redis_client.delete(_session_key(uid))
        except Exception:
            pass

        cursor = 0
        try:
            while True:
                cursor, pairs = await redis_client.zscan(zkey, cursor=cursor, count=200)
                for member, _score in pairs:
                    mid = str(member)

                    if mid in targets:
                        try:
                            await redis_client.zrem(zkey, mid)
                            await redis_client.delete(_session_key(mid))
                        except Exception:
                            pass
                        continue

                    session = await self.get_session(mid)
                    if session is None:
                        try:
                            await redis_client.zrem(zkey, mid)
                        except Exception:
                            pass
                        continue

                    if str(session.user_id) in targets:
                        try:
                            await redis_client.zrem(zkey, mid)
                            await redis_client.delete(_session_key(mid))
                            await redis_client.delete(_session_key(str(session.user_id)))
                        except Exception:
                            pass

                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"在线会话批量按用户清理失败(REDIS): {e}")

    async def list_online(
        self, *, page: int, page_size: int, keyword: str | None = None
    ) -> tuple[list[OnlineSession], int]:
        if redis_client is None:
            return [], 0

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        zkey = _online_zset_key()

        # 全量扫描并去重：保证同一 user_id 只返回一条，并顺手清理脏数据
        sessions_by_user: dict[str, OnlineSession] = {}
        cursor = 0
        try:
            while True:
                cursor, pairs = await redis_client.zscan(zkey, cursor=cursor, count=500)
                for member, _score in pairs:
                    mid = str(member)
                    session = await self.get_session(mid)

                    if session is None:
                        # member 对应的 session key 已过期/不存在：清理 zset 成员
                        try:
                            await redis_client.zrem(zkey, mid)
                        except Exception:
                            pass
                        continue

                    # 兼容历史数据：member 可能不是 user_id（例如 session_id）
                    if mid != str(session.user_id):
                        try:
                            # 迁移为规范 member=user_id
                            await redis_client.zadd(zkey, {str(session.user_id): float(session.last_seen_at)})
                            await redis_client.setex(
                                _session_key(str(session.user_id)),
                                max(1, int(_default_online_ttl_seconds())),
                                json.dumps(asdict(session), ensure_ascii=False),
                            )
                            await redis_client.zrem(zkey, mid)
                            await redis_client.delete(_session_key(mid))
                        except Exception:
                            pass

                    uid = str(session.user_id)
                    existing = sessions_by_user.get(uid)
                    if existing is None or float(session.last_seen_at) > float(existing.last_seen_at):
                        sessions_by_user[uid] = session

                if cursor == 0:
                    break
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
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # user_id -> (session, expire_at)
        self._data: dict[str, tuple[OnlineSession, float]] = {}

    async def upsert_session(self, session: OnlineSession, ttl_seconds: int) -> None:
        expire_at = time.time() + max(1, int(ttl_seconds))
        async with self._lock:
            self._data[session.user_id] = (session, expire_at)

    async def get_session(self, user_id: str) -> OnlineSession | None:
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
    return _redis_store if redis_client is not None else _memory_store


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
