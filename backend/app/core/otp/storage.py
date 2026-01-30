"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 存储模块 (OTP Storage).

提供 OTP 相关的 Redis 键名生成和 Redis 操作封装。
"""

import json
from typing import Any, Mapping
from uuid import UUID

from app.core import cache as cache_module
from app.core.logger import logger

OTP_CACHE_PREFIX = "ncm:otp:v1:cache"
OTP_WAIT_LOCK_PREFIX = "ncm:otp:v1:wait:lock"
OTP_WAIT_STATE_PREFIX = "ncm:otp:v1:wait:state"
OTP_TASK_PAUSE_PREFIX = "ncm:otp:v1:task:pause"
OTP_BATCH_PREFIX = "ncm:otp:v1:task:batch"


def _normalize_group(device_group: str) -> str:
    """
    规范化设备分组名称。

    移除 "DeviceGroup." 前缀并转换为小写。

    Args:
        device_group: 设备分组名称

    Returns:
        str: 规范化后的设备分组名称
    """
    raw = str(device_group)
    if raw.startswith("DeviceGroup."):
        raw = raw.split(".", maxsplit=1)[-1]
    return raw.lower()


def otp_cache_key(dept_id: UUID, device_group: str) -> str:
    """
    生成 OTP 缓存键名。

    Args:
        dept_id: 部门 ID
        device_group: 设备分组

    Returns:
        str: Redis 键名
    """
    return f"{OTP_CACHE_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_wait_lock_key(dept_id: UUID, device_group: str) -> str:
    """
    生成 OTP 等待锁键名。

    Args:
        dept_id: 部门 ID
        device_group: 设备分组

    Returns:
        str: Redis 键名
    """
    return f"{OTP_WAIT_LOCK_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_wait_state_key(dept_id: UUID, device_group: str) -> str:
    """
    生成 OTP 等待状态键名。

    Args:
        dept_id: 部门 ID
        device_group: 设备分组

    Returns:
        str: Redis 键名
    """
    return f"{OTP_WAIT_STATE_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_task_pause_key(task_id: str, dept_id: UUID, device_group: str) -> str:
    """
    生成 OTP 任务暂停状态键名。

    Args:
        task_id: 任务 ID
        dept_id: 部门 ID
        device_group: 设备分组

    Returns:
        str: Redis 键名
    """
    return f"{OTP_TASK_PAUSE_PREFIX}:{task_id}:{dept_id}:{_normalize_group(device_group)}"


def otp_batch_key(batch_id: str) -> str:
    """
    生成 OTP 批量任务键名。

    Args:
        batch_id: 批次 ID

    Returns:
        str: Redis 键名
    """
    return f"{OTP_BATCH_PREFIX}:{batch_id}"


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
