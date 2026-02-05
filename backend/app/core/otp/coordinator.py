"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: coordinator.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 协调器模块 (OTP Coordinator).

统一管理 OTP 验证码的缓存、等待状态与任务暂停功能。
"""

import time
from typing import cast
from uuid import UUID

from app.core.config import settings
from app.core.logger import logger

from .registry import OtpTaskRegistry
from .storage import (
    otp_cache_key_by_credential,
    otp_task_pause_key_by_credential,
    otp_wait_lock_key_by_credential,
    otp_wait_state_key_by_credential,
    redis_delete,
    redis_expire,
    redis_get,
    redis_json_get,
    redis_json_set,
    redis_setex,
    redis_setnx_ex,
    redis_ttl,
)
from .types import OtpAcquireResult, OtpPauseState, OtpWaitState, OtpWaitStatus


class OtpCoordinator:
    """
    OTP 协调器类。

    统一管理 OTP 验证码的缓存、等待状态与任务暂停功能。
    提供 OTP 获取、缓存、等待状态管理、任务暂停/恢复等功能。
    """

    def __init__(self, cache_ttl: int | None = None, wait_timeout: int | None = None):
        """
        初始化 OTP 协调器。

        Args:
            cache_ttl: OTP 缓存 TTL（秒，可选，默认使用配置值）
            wait_timeout: OTP 等待超时时间（秒，可选，默认使用配置值）
        """
        self.cache_ttl = cache_ttl or settings.OTP_CACHE_TTL_SECONDS
        self.wait_timeout = wait_timeout or settings.OTP_WAIT_TIMEOUT_SECONDS
        self.pause_ttl = self.wait_timeout  # 暂停状态 TTL 与等待超时一致
        self.registry = OtpTaskRegistry()

    async def get_cached_otp(self, credential_id: UUID) -> str | None:
        """
        获取缓存的 OTP 验证码。

        Args:
            credential_id: 凭据 ID

        Returns:
            str | None: OTP 验证码，如果不存在则返回 None
        """
        raw = await redis_get(otp_cache_key_by_credential(credential_id))
        return raw if raw else None

    async def cache_otp(self, credential_id: UUID, otp_code: str) -> int:
        """
        缓存 OTP 验证码。

        缓存成功后会自动清除等待状态并释放等待锁。

        Args:
            credential_id: 凭据 ID
            otp_code: OTP 验证码

        Returns:
            int: 缓存 TTL（秒），如果缓存失败则返回 0
        """
        ok = await redis_setex(otp_cache_key_by_credential(credential_id), self.cache_ttl, otp_code)
        if ok:
            await self.clear_wait_state(credential_id)
            await self.release_wait_lock(credential_id)
            logger.info("OTP 已缓存", credential_id=str(credential_id))
            return self.cache_ttl
        logger.warning("OTP 缓存失败", credential_id=str(credential_id))
        return 0

    async def invalidate_otp(self, credential_id: UUID) -> None:
        """
        使 OTP 验证码失效（删除缓存）。

        Args:
            credential_id: 凭据 ID
        """
        await redis_delete(otp_cache_key_by_credential(credential_id))

    async def extend_otp_ttl(self, credential_id: UUID, additional_seconds: int = 300) -> int:
        """
        延长 OTP 缓存的 TTL。

        用于批量任务场景，确保同一 credential_id 的多个任务
        都能在 OTP 过期前完成。

        Args:
            credential_id: 凭据 ID
            additional_seconds: 额外延长的秒数（默认 300 秒 = 5 分钟）

        Returns:
            int: 新的 TTL（秒），如果失败则返回 0
        """
        cache_key = otp_cache_key_by_credential(credential_id)
        current_ttl = await redis_ttl(cache_key)

        # 键不存在或已过期
        if current_ttl < 0:
            return 0

        # 计算新的 TTL（当前剩余 + 额外延长）
        new_ttl = current_ttl + additional_seconds
        ok = await redis_expire(cache_key, new_ttl)
        if ok:
            logger.debug(
                "OTP TTL 已延长",
                credential_id=str(credential_id),
                previous_ttl=current_ttl,
                new_ttl=new_ttl,
            )
            return new_ttl
        return 0

    async def acquire_wait_lock(self, credential_id: UUID) -> bool:
        """
        获取等待锁（分布式锁，防止并发等待）。

        Args:
            credential_id: 凭据 ID

        Returns:
            bool: 是否成功获取锁
        """
        return await redis_setnx_ex(otp_wait_lock_key_by_credential(credential_id), self.wait_timeout, "1")

    async def release_wait_lock(self, credential_id: UUID) -> None:
        """
        释放等待锁。

        Args:
            credential_id: 凭据 ID
        """
        await redis_delete(otp_wait_lock_key_by_credential(credential_id))

    def _build_waiting_state(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        """
        构建等待状态字典。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）

        Returns:
            OtpWaitState: 等待状态字典
        """
        now_ts = time.time()
        return {
            "status": OtpWaitStatus.WAITING.value,
            "notified": False,
            "credential_id": str(credential_id),
            "task_id": task_id,
            "pending_device_ids": pending_device_ids,
            "started_at": now_ts,
            "expires_at": now_ts + self.wait_timeout,
            "timeout_seconds": self.wait_timeout,
        }

    def _build_timeout_state(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        """
        构建超时状态字典。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）

        Returns:
            OtpWaitState: 超时状态字典
        """
        now_ts = time.time()
        return {
            "status": OtpWaitStatus.TIMEOUT.value,
            "notified": False,
            "credential_id": str(credential_id),
            "task_id": task_id,
            "pending_device_ids": pending_device_ids,
            "message": "用户未提供 OTP 验证码，连接失败",
            "started_at": now_ts,
            "expires_at": now_ts + self.wait_timeout,
            "timeout_seconds": self.wait_timeout,
        }

    async def _ensure_wait_state(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        """
        确保等待状态存在（如果不存在则创建，如果已过期则更新为超时状态）。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）

        Returns:
            OtpWaitState: 等待状态字典
        """
        state = await redis_json_get(otp_wait_state_key_by_credential(credential_id))
        now_ts = time.time()
        if state:
            state = cast(OtpWaitState, state)
            expires_at = float(state.get("expires_at") or 0)
            if state.get("status") == OtpWaitStatus.WAITING.value and expires_at and now_ts > expires_at:
                state = self._build_timeout_state(
                    credential_id,
                    task_id=task_id or state.get("task_id"),
                    pending_device_ids=pending_device_ids or state.get("pending_device_ids"),
                )
                await redis_json_set(otp_wait_state_key_by_credential(credential_id), self.wait_timeout, state)
            return state

        await self.acquire_wait_lock(credential_id)
        state = self._build_waiting_state(
            credential_id,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        await redis_json_set(otp_wait_state_key_by_credential(credential_id), self.wait_timeout, state)
        return state

    async def clear_wait_state(self, credential_id: UUID) -> None:
        """
        清除等待状态。

        Args:
            credential_id: 凭据 ID
        """
        await redis_delete(otp_wait_state_key_by_credential(credential_id))

    async def should_notify_group(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> bool:
        """
        判断是否应该通知该设备组（首次等待时返回 True，后续返回 False）。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）

        Returns:
            bool: 是否应该通知（首次等待返回 True）
        """
        state = await self._ensure_wait_state(credential_id, task_id=task_id, pending_device_ids=pending_device_ids)
        if state.get("notified"):
            return False
        state["notified"] = True
        now_ts = time.time()
        expires_at = float(state.get("expires_at") or (now_ts + self.wait_timeout))
        ttl_seconds = max(1, int(expires_at - now_ts))
        await redis_json_set(otp_wait_state_key_by_credential(credential_id), ttl_seconds, state)
        return True

    async def get_or_require_otp(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpAcquireResult:
        """
        获取或要求 OTP 验证码。

        如果缓存中存在 OTP，直接返回；否则创建等待状态并返回等待结果。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）

        Returns:
            OtpAcquireResult: OTP 获取结果，包含状态、验证码和是否应该通知
        """
        otp_code = await self.get_cached_otp(credential_id)
        if otp_code:
            return {"status": "ready", "otp_code": otp_code, "should_notify": False}

        state = await self._ensure_wait_state(
            credential_id,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        status = "timeout" if state.get("status") == OtpWaitStatus.TIMEOUT.value else "waiting"
        should_notify = await self.should_notify_group(
            credential_id,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        return {"status": status, "otp_code": None, "should_notify": should_notify}

    async def mark_group_timeout(
        self,
        credential_id: UUID,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> None:
        """
        标记设备组为超时状态。

        Args:
            credential_id: 凭据 ID
            task_id: 任务 ID（可选）
            pending_device_ids: 待处理设备 ID 列表（可选）
        """
        state = self._build_timeout_state(
            credential_id,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        await redis_json_set(otp_wait_state_key_by_credential(credential_id), self.wait_timeout, state)

    async def record_pause(
        self,
        task_id: str,
        credential_id: UUID,
        pending_device_ids: list[str],
        *,
        reason: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """
        记录任务暂停状态。

        Args:
            task_id: 任务 ID
            credential_id: 凭据 ID
            pending_device_ids: 待处理设备 ID 列表
            reason: 暂停原因（可选）
            extra: 额外信息（可选）
        """
        payload: OtpPauseState = {
            "task_id": task_id,
            "credential_id": str(credential_id),
            "pending_device_ids": [str(x) for x in pending_device_ids],
            "paused_at": time.time(),
            "reason": reason,
            "extra": extra,
        }
        await redis_json_set(otp_task_pause_key_by_credential(task_id, credential_id), self.pause_ttl, payload)

    async def get_pause(self, task_id: str, credential_id: UUID) -> OtpPauseState | None:
        """
        获取任务暂停状态。

        Args:
            task_id: 任务 ID
            credential_id: 凭据 ID

        Returns:
            OtpPauseState | None: 暂停状态，如果不存在则返回 None
        """
        pause_state = await redis_json_get(otp_task_pause_key_by_credential(task_id, credential_id))
        return cast(OtpPauseState, pause_state) if pause_state else None

    async def clear_pause(self, task_id: str, credential_id: UUID) -> None:
        """
        清除任务暂停状态。

        Args:
            task_id: 任务 ID
            credential_id: 凭据 ID
        """
        await redis_delete(otp_task_pause_key_by_credential(task_id, credential_id))

    async def resume_group(self, task_id: str, credential_id: UUID) -> OtpPauseState | None:
        """
        恢复设备组（清除暂停状态、等待状态和等待锁）。

        Args:
            task_id: 任务 ID
            credential_id: 凭据 ID

        Returns:
            OtpPauseState | None: 恢复前的暂停状态，如果不存在则返回 None
        """
        pause_state = await self.get_pause(task_id, credential_id)
        await self.clear_pause(task_id, credential_id)
        await self.clear_wait_state(credential_id)
        await self.release_wait_lock(credential_id)
        return pause_state


# 全局 OTP 协调器实例
otp_coordinator = OtpCoordinator()
