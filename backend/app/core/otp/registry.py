import time
from typing import Any

from app.core.logger import logger

from .storage import otp_batch_key, redis_json_get, redis_json_set

DEFAULT_BATCH_TTL_SECONDS = 24 * 60 * 60


class OtpTaskRegistry:
    """OTP 批量任务注册表。"""

    def __init__(self, ttl_seconds: int = DEFAULT_BATCH_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    async def create_batch(self, batch_id: str, payload: dict[str, Any]) -> bool:
        data = {
            **payload,
            "batch_id": batch_id,
            "created_at": time.time(),
        }
        return await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, data)

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        return await redis_json_get(otp_batch_key(batch_id))

    async def append_children(self, batch_id: str, children: list[dict[str, Any]]) -> bool:
        batch = await self.get_batch(batch_id)
        if not batch:
            return False
        merged_children = list(batch.get("children") or [])
        merged_children.extend(children)
        batch["children"] = merged_children
        batch["updated_at"] = time.time()
        ok = await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, batch)
        if not ok:
            logger.warning("更新批量任务失败", batch_id=batch_id)
        return ok
