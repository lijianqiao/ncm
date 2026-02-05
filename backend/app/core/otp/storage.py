"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 存储模块 (OTP Storage).

提供 OTP 相关的 Redis 键名生成和 Redis 操作封装。
"""

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.core import cache as cache_module
from app.core.logger import logger

OTP_CACHE_PREFIX_V2 = "ncm:otp:v2:cache"
OTP_WAIT_LOCK_PREFIX_V2 = "ncm:otp:v2:wait:lock"
OTP_WAIT_STATE_PREFIX_V2 = "ncm:otp:v2:wait:state"
OTP_TASK_PAUSE_PREFIX_V2 = "ncm:otp:v2:task:pause"
OTP_BATCH_PREFIX_V2 = "ncm:otp:v2:task:batch"


def otp_cache_key_by_credential(credential_id: UUID | str) -> str:
    """
    生成 OTP 缓存键名（按凭据 ID）。

    Args:
        credential_id: 设备凭据 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_CACHE_PREFIX_V2}:{credential_id}"


def otp_wait_lock_key_by_credential(credential_id: UUID | str) -> str:
    """
    生成 OTP 等待锁键名（按凭据 ID）。

    Args:
        credential_id: 设备凭据 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_WAIT_LOCK_PREFIX_V2}:{credential_id}"


def otp_wait_state_key_by_credential(credential_id: UUID | str) -> str:
    """
    生成 OTP 等待状态键名（按凭据 ID）。

    Args:
        credential_id: 设备凭据 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_WAIT_STATE_PREFIX_V2}:{credential_id}"


def otp_task_pause_key_by_credential(task_id: str, credential_id: UUID | str) -> str:
    """
    生成 OTP 任务暂停状态键名（按凭据 ID）。

    Args:
        task_id: 任务 ID
        credential_id: 设备凭据 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_TASK_PAUSE_PREFIX_V2}:{task_id}:{credential_id}"


def otp_batch_key(batch_id: str) -> str:
    """
    生成 OTP 批量任务键名。

    Args:
        batch_id: 批次 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_BATCH_PREFIX_V2}:{batch_id}"


async def redis_get(key: str) -> str | None:
    """
    从 Redis 获取字符串值。

    Args:
        key: Redis 键名

    Returns:
        str | None: 值，如果不存在或出错则返回 None
    """
    client = cache_module.redis_client
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception as exc:
        logger.warning("读取 Redis 失败", key=key, error=str(exc))
        return None


async def redis_setex(key: str, ttl_seconds: int, value: str) -> bool:
    """
    设置 Redis 键值对（带过期时间）。

    Args:
        key: Redis 键名
        ttl_seconds: 过期时间（秒）
        value: 值

    Returns:
        bool: 是否设置成功
    """
    client = cache_module.redis_client
    if client is None:
        return False
    try:
        await client.setex(key, max(1, int(ttl_seconds)), value)
        return True
    except Exception as exc:
        logger.warning("写入 Redis 失败", key=key, error=str(exc))
        return False


async def redis_setnx_ex(key: str, ttl_seconds: int, value: str) -> bool:
    """
    设置 Redis 键值对（仅当键不存在时，带过期时间）。

    用于实现分布式锁。

    Args:
        key: Redis 键名
        ttl_seconds: 过期时间（秒）
        value: 值

    Returns:
        bool: 是否设置成功（键不存在时返回 True，已存在时返回 False）
    """
    client = cache_module.redis_client
    if client is None:
        return False
    try:
        ok = await client.set(key, value, ex=max(1, int(ttl_seconds)), nx=True)
        return bool(ok)
    except Exception as exc:
        logger.warning("写入 Redis NX 失败", key=key, error=str(exc))
        return False


async def redis_delete(key: str) -> bool:
    """
    删除 Redis 键。

    Args:
        key: Redis 键名

    Returns:
        bool: 是否删除成功
    """
    client = cache_module.redis_client
    if client is None:
        return False
    try:
        deleted = await client.delete(key)
        return bool(deleted)
    except Exception as exc:
        logger.warning("删除 Redis 失败", key=key, error=str(exc))
        return False


async def redis_ttl(key: str) -> int:
    """
    获取 Redis 键的剩余 TTL。

    Args:
        key: Redis 键名

    Returns:
        int: 剩余秒数。-2 表示键不存在，-1 表示无过期时间。
    """
    client = cache_module.redis_client
    if client is None:
        return -2
    try:
        ttl = await client.ttl(key)
        return ttl if ttl is not None else -2
    except Exception as exc:
        logger.warning("获取 Redis TTL 失败", key=key, error=str(exc))
        return -2


async def redis_expire(key: str, ttl_seconds: int) -> bool:
    """
    设置 Redis 键的过期时间。

    Args:
        key: Redis 键名
        ttl_seconds: 过期时间（秒）

    Returns:
        bool: 是否设置成功（键存在时返回 True，不存在时返回 False）
    """
    client = cache_module.redis_client
    if client is None:
        return False
    try:
        ok = await client.expire(key, max(1, int(ttl_seconds)))
        return bool(ok)
    except Exception as exc:
        logger.warning("设置 Redis 过期时间失败", key=key, error=str(exc))
        return False


async def redis_json_get(key: str) -> dict[str, Any] | None:
    """
    从 Redis 获取 JSON 值并解析为字典。

    Args:
        key: Redis 键名

    Returns:
        dict[str, Any] | None: 解析后的字典，如果不存在或解析失败则返回 None
    """
    raw = await redis_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        logger.warning("解析 Redis JSON 失败", key=key, error=str(exc))
        return None


async def redis_json_set(key: str, ttl_seconds: int, payload: Mapping[str, Any]) -> bool:
    """
    将字典序列化为 JSON 并存储到 Redis（带过期时间）。

    Args:
        key: Redis 键名
        ttl_seconds: 过期时间（秒）
        payload: 要存储的字典

    Returns:
        bool: 是否存储成功
    """
    try:
        raw = json.dumps(dict(payload), ensure_ascii=False)
    except Exception as exc:
        logger.warning("序列化 Redis JSON 失败", key=key, error=str(exc))
        return False
    return await redis_setex(key, ttl_seconds, raw)
