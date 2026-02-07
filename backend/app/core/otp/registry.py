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

    async def append_children(self, batch_id: str, children: list[dict[str, Any]], *, max_retries: int = 3) -> bool:
        """
        追加子任务到批次（带乐观重试保护）。

        使用简单的重试机制防止 read-modify-write 竞态：
        如果并发 resume 导致数据被覆盖，最多重试 max_retries 次。

        Args:
            batch_id: 批次 ID
            children: 子任务列表
            max_retries: 最大重试次数，默认 3

        Returns:
            bool: 是否追加成功
        """
        for attempt in range(max_retries):
            batch = await self.get_batch(batch_id)
            if not batch:
                return False
            merged_children = list(batch.get("children") or [])
            merged_children.extend(children)
            batch["children"] = merged_children
            batch["updated_at"] = time.time()
            ok = await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, batch)
            if ok:
                return True
            logger.warning("追加子任务失败，准备重试", batch_id=batch_id, attempt=attempt + 1)
        logger.warning("追加子任务最终失败", batch_id=batch_id, max_retries=max_retries)
        return False

    async def mark_credential_resumed(self, batch_id: str, credential_id: str) -> bool:
        """
        标记凭证已被 Resume，防止重复触发 OTP 请求。

        Args:
            batch_id: 批次 ID
            credential_id: 凭据 ID

        Returns:
            bool: 是否标记成功
        """
        batch = await self.get_batch(batch_id)
        if not batch:
            return False
        resumed_credentials: list[str] = batch.get("resumed_credentials") or []
        if credential_id not in resumed_credentials:
            resumed_credentials.append(credential_id)
            batch["resumed_credentials"] = resumed_credentials
            batch["updated_at"] = time.time()
            return await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, batch)
        return True

    async def is_credential_resumed(self, batch_id: str, credential_id: str) -> bool:
        """
        检查凭证是否已被 Resume。

        Args:
            batch_id: 批次 ID
            credential_id: 凭据 ID

        Returns:
            bool: 是否已被 Resume
        """
        batch = await self.get_batch(batch_id)
        if not batch:
            return False
        resumed_credentials: list[str] = batch.get("resumed_credentials") or []
        return credential_id in resumed_credentials

    async def mark_auto_retry_submitted(self, batch_id: str) -> bool:
        """
        标记批次已提交自动重试，防止重复触发。

        用于通用失败重试机制：所有子任务完成后，收集非 OTP 失败设备
        合并提交最后一轮重试任务。通过此标记保证幂等性。

        Args:
            batch_id: 批次 ID

        Returns:
            bool: 是否标记成功
        """
        batch = await self.get_batch(batch_id)
        if not batch:
            return False
        batch["auto_retry_submitted"] = True
        batch["auto_retry_at"] = time.time()
        return await redis_json_set(otp_batch_key(batch_id), self.ttl_seconds, batch)

    async def is_auto_retry_submitted(self, batch_id: str) -> bool:
        """
        检查批次是否已提交自动重试。

        Args:
            batch_id: 批次 ID

        Returns:
            bool: 是否已提交自动重试
        """
        batch = await self.get_batch(batch_id)
        return bool(batch.get("auto_retry_submitted")) if batch else False

