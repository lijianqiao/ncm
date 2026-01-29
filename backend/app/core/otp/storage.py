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
    raw = str(device_group)
    if raw.startswith("DeviceGroup."):
        raw = raw.split(".", maxsplit=1)[-1]
    return raw.lower()


def otp_cache_key(dept_id: UUID, device_group: str) -> str:
    return f"{OTP_CACHE_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_wait_lock_key(dept_id: UUID, device_group: str) -> str:
    return f"{OTP_WAIT_LOCK_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_wait_state_key(dept_id: UUID, device_group: str) -> str:
    return f"{OTP_WAIT_STATE_PREFIX}:{dept_id}:{_normalize_group(device_group)}"


def otp_task_pause_key(task_id: str, dept_id: UUID, device_group: str) -> str:
    return f"{OTP_TASK_PAUSE_PREFIX}:{task_id}:{dept_id}:{_normalize_group(device_group)}"


def otp_batch_key(batch_id: str) -> str:
    return f"{OTP_BATCH_PREFIX}:{batch_id}"


async def redis_get(key: str) -> str | None:
    client = cache_module.redis_client
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception as exc:
        logger.warning("读取 Redis 失败", key=key, error=str(exc))
        return None


async def redis_setex(key: str, ttl_seconds: int, value: str) -> bool:
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
    raw = await redis_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        logger.warning("解析 Redis JSON 失败", key=key, error=str(exc))
        return None


async def redis_json_set(key: str, ttl_seconds: int, payload: Mapping[str, Any]) -> bool:
    try:
        raw = json.dumps(dict(payload), ensure_ascii=False)
    except Exception as exc:
        logger.warning("序列化 Redis JSON 失败", key=key, error=str(exc))
        return False
    return await redis_setex(key, ttl_seconds, raw)
