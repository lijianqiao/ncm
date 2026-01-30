"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: registry.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 任务注册表模块 (OTP Task Registry).

提供 OTP 批量任务的注册和管理功能。
"""

import time
from typing import Any

from app.core.logger import logger

from .storage import otp_batch_key, redis_json_get, redis_json_set

DEFAULT_BATCH_TTL_SECONDS = 24 * 60 * 60


class OtpTaskRegistry:
    """
    OTP 批量任务注册表类。

    用于注册和管理 OTP 批量任务，支持创建批次、获取批次信息和追加子任务。
    """

    def __init__(self, ttl_seconds: int = DEFAULT_BATCH_TTL_SECONDS):
        """
        初始化 OTP 任务注册表。

        Args:
            ttl_seconds: 批次数据 TTL（秒，默认 24 小时）
        """
        self.ttl_seconds = ttl_seconds

    async def create_batch(self, batch_id: str, payload: dict[str, Any]) -> bool:
        """
        创建批量任务批次。

        Args:
            batch_id: 批次 ID
            payload: 批次数据

        Returns:
            bool: 是否创建成功
        """
        data = {
            **payload,
            "batch_id": batch_id,
            "created_at": time.time(),
        }
        return await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, data)

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        """
        获取批量任务批次信息。

        Args:
            batch_id: 批次 ID

        Returns:
            dict[str, Any] | None: 批次数据，如果不存在则返回 None
        """
        return await redis_json_get(otp_batch_key(batch_id))

    async def append_children(self, batch_id: str, children: list[dict[str, Any]]) -> bool:
        """
        追加子任务到批次。

        Args:
            batch_id: 批次 ID
            children: 子任务列表

        Returns:
            bool: 是否追加成功
        """
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
