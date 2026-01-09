"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: cache.py
@DateTime: 2025-12-30 15:20:00
@Docs: Redis 缓存模块 (Cache System with Decorator).
"""

import functools
import hashlib
import json
from collections.abc import Callable, Iterable
from typing import Any, TypeVar
from uuid import UUID

import redis.asyncio as redis

from app.core.config import settings
from app.core.logger import logger

RT = TypeVar("RT")

# Redis 连接池 (应用启动时初始化)
redis_pool: redis.ConnectionPool | None = None
redis_client: redis.Redis | None = None


async def init_redis() -> None:
    """
    初始化 Redis 连接池。应在应用启动时调用。
    """
    global redis_pool, redis_client
    try:
        redis_pool = redis.ConnectionPool.from_url(
            str(settings.REDIS_URL),
            decode_responses=True,
            max_connections=10,
        )
        redis_client = redis.Redis(connection_pool=redis_pool)
        await redis_client.ping()  # type: ignore
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 连接失败，缓存功能将被禁用: {e}")
        redis_client = None


async def close_redis() -> None:
    """
    关闭 Redis 连接。应在应用关闭时调用。
    """
    global redis_client, redis_pool
    if redis_client:
        await redis_client.aclose()
    if redis_pool:
        await redis_pool.disconnect()
    logger.info("Redis 连接已关闭")


def _generate_cache_key(prefix: str, func: Callable, args: tuple, kwargs: dict) -> str:
    """
    根据函数名和参数生成缓存 Key。
    """
    # 排除 self 参数
    key_args = args[1:] if args and hasattr(args[0], "__class__") else args
    key_data = {"args": str(key_args), "kwargs": str(sorted(kwargs.items()))}
    key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:16]
    return f"{prefix}:{func.__module__}.{func.__qualname__}:{key_hash}"


def cache(prefix: str = "cache", expire: int = 300) -> Callable:
    """
    缓存装饰器。

    Args:
        prefix: 缓存 Key 前缀 (如 v1:menu)。
        expire: 过期时间 (秒)，默认 5 分钟。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if redis_client is None:
                # Redis 未初始化，直接执行原函数
                return await func(*args, **kwargs)

            cache_key = _generate_cache_key(prefix, func, args, kwargs)

            try:
                # 尝试从缓存获取
                cached_value = await redis_client.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"缓存命中: {cache_key}")
                    return json.loads(cached_value)
            except Exception as e:
                logger.warning(f"缓存读取错误: {e}")

            # 缓存未命中，执行原函数
            result = await func(*args, **kwargs)

            try:
                # 将结果写入缓存
                # 注意: 对于 ORM 对象，需要先序列化
                await redis_client.setex(cache_key, expire, json.dumps(result, default=str))  # type: ignore
                logger.debug(f"缓存写入: {cache_key}")
            except Exception as e:
                logger.warning(f"缓存写入错误: {e}")

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str) -> int:
    """
    根据 Key 模式失效缓存。

    Args:
        pattern: Redis Key 模式 (如 "v1:menu:*")。

    Returns:
        int: 删除的 Key 数量。
    """
    if redis_client is None:
        return 0

    deleted = 0
    try:
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)  # type: ignore
            deleted += 1
        if deleted > 0:
            logger.info(f"缓存失效: {pattern}, 已删除 {deleted} 个键")
    except Exception as e:
        logger.warning(f"缓存失效错误: {e}")
    return deleted


def user_permissions_cache_key(user_id: UUID) -> str:
    return f"v1:user:permissions:{user_id}"


async def invalidate_user_permissions_cache(user_ids: Iterable[UUID]) -> int:
    """精确失效指定用户的权限缓存。"""

    if redis_client is None:
        return 0

    ids = list(user_ids)
    if not ids:
        return 0

    deleted = 0
    try:
        for user_id in ids:
            key = user_permissions_cache_key(user_id)
            deleted += int(await redis_client.delete(key))  # type: ignore
        if deleted > 0:
            logger.info(f"权限缓存失效: users={len(ids)}, deleted={deleted}")
    except Exception as e:
        logger.warning(f"权限缓存失效错误: {e}")
    return deleted
