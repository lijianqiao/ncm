import time
from typing import cast
from uuid import UUID

from app.core.config import settings
from app.core.logger import logger

from .registry import OtpTaskRegistry
from .storage import (
    otp_cache_key,
    otp_task_pause_key,
    otp_wait_lock_key,
    otp_wait_state_key,
    redis_delete,
    redis_get,
    redis_json_get,
    redis_json_set,
    redis_setex,
    redis_setnx_ex,
)
from .types import OtpAcquireResult, OtpPauseState, OtpWaitState, OtpWaitStatus


class OtpCoordinator:
    """OTP 协调器，统一缓存、等待状态与任务暂停。"""

    def __init__(self, cache_ttl: int | None = None, wait_timeout: int | None = None):
        self.cache_ttl = cache_ttl or settings.OTP_CACHE_TTL_SECONDS
        self.wait_timeout = wait_timeout or settings.OTP_WAIT_TIMEOUT_SECONDS
        self.pause_ttl = max(self.wait_timeout * 10, 6 * 60 * 60)
        self.registry = OtpTaskRegistry()

    async def get_cached_otp(self, dept_id: UUID, device_group: str) -> str | None:
        raw = await redis_get(otp_cache_key(dept_id, device_group))
        return raw if raw else None

    async def cache_otp(self, dept_id: UUID, device_group: str, otp_code: str) -> int:
        ok = await redis_setex(otp_cache_key(dept_id, device_group), self.cache_ttl, otp_code)
        if ok:
            await self.clear_wait_state(dept_id, device_group)
            await self.release_wait_lock(dept_id, device_group)
            logger.info("OTP 已缓存", dept_id=str(dept_id), device_group=str(device_group))
            return self.cache_ttl
        logger.warning("OTP 缓存失败", dept_id=str(dept_id), device_group=str(device_group))
        return 0

    async def invalidate_otp(self, dept_id: UUID, device_group: str) -> None:
        await redis_delete(otp_cache_key(dept_id, device_group))

    async def acquire_wait_lock(self, dept_id: UUID, device_group: str) -> bool:
        return await redis_setnx_ex(otp_wait_lock_key(dept_id, device_group), self.wait_timeout, "1")

    async def release_wait_lock(self, dept_id: UUID, device_group: str) -> None:
        await redis_delete(otp_wait_lock_key(dept_id, device_group))

    def _build_waiting_state(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        now_ts = time.time()
        return {
            "status": OtpWaitStatus.WAITING.value,
            "notified": False,
            "dept_id": str(dept_id),
            "device_group": str(device_group),
            "task_id": task_id,
            "pending_device_ids": pending_device_ids,
            "started_at": now_ts,
            "expires_at": now_ts + self.wait_timeout,
            "timeout_seconds": self.wait_timeout,
        }

    def _build_timeout_state(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        now_ts = time.time()
        return {
            "status": OtpWaitStatus.TIMEOUT.value,
            "notified": False,
            "dept_id": str(dept_id),
            "device_group": str(device_group),
            "task_id": task_id,
            "pending_device_ids": pending_device_ids,
            "message": "用户未提供 OTP 验证码，连接失败",
            "started_at": now_ts,
            "expires_at": now_ts + self.wait_timeout,
            "timeout_seconds": self.wait_timeout,
        }

    async def _ensure_wait_state(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpWaitState:
        state = await redis_json_get(otp_wait_state_key(dept_id, device_group))
        now_ts = time.time()
        if state:
            state = cast(OtpWaitState, state)
            expires_at = float(state.get("expires_at") or 0)
            if state.get("status") == OtpWaitStatus.WAITING.value and expires_at and now_ts > expires_at:
                state = self._build_timeout_state(
                    dept_id,
                    device_group,
                    task_id=task_id or state.get("task_id"),
                    pending_device_ids=pending_device_ids or state.get("pending_device_ids"),
                )
                await redis_json_set(otp_wait_state_key(dept_id, device_group), self.wait_timeout, state)
            return state

        await self.acquire_wait_lock(dept_id, device_group)
        state = self._build_waiting_state(
            dept_id,
            device_group,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        await redis_json_set(otp_wait_state_key(dept_id, device_group), self.wait_timeout, state)
        return state

    async def clear_wait_state(self, dept_id: UUID, device_group: str) -> None:
        await redis_delete(otp_wait_state_key(dept_id, device_group))

    async def should_notify_group(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> bool:
        state = await self._ensure_wait_state(
            dept_id,
            device_group,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        if state.get("notified"):
            return False
        state["notified"] = True
        now_ts = time.time()
        expires_at = float(state.get("expires_at") or (now_ts + self.wait_timeout))
        ttl_seconds = max(1, int(expires_at - now_ts))
        await redis_json_set(otp_wait_state_key(dept_id, device_group), ttl_seconds, state)
        return True

    async def get_or_require_otp(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> OtpAcquireResult:
        otp_code = await self.get_cached_otp(dept_id, device_group)
        if otp_code:
            return {"status": "ready", "otp_code": otp_code, "should_notify": False}

        state = await self._ensure_wait_state(
            dept_id,
            device_group,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        status = "timeout" if state.get("status") == OtpWaitStatus.TIMEOUT.value else "waiting"
        should_notify = await self.should_notify_group(
            dept_id,
            device_group,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        return {"status": status, "otp_code": None, "should_notify": should_notify}

    async def mark_group_timeout(
        self,
        dept_id: UUID,
        device_group: str,
        *,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ) -> None:
        state = self._build_timeout_state(
            dept_id,
            device_group,
            task_id=task_id,
            pending_device_ids=pending_device_ids,
        )
        await redis_json_set(otp_wait_state_key(dept_id, device_group), self.wait_timeout, state)

    async def record_pause(
        self,
        task_id: str,
        dept_id: UUID,
        device_group: str,
        pending_device_ids: list[str],
        *,
        reason: str | None = None,
        extra: dict | None = None,
    ) -> None:
        payload: OtpPauseState = {
            "task_id": task_id,
            "dept_id": str(dept_id),
            "device_group": str(device_group),
            "pending_device_ids": [str(x) for x in pending_device_ids],
            "paused_at": time.time(),
            "reason": reason,
            "extra": extra,
        }
        await redis_json_set(otp_task_pause_key(task_id, dept_id, device_group), self.pause_ttl, payload)

    async def get_pause(self, task_id: str, dept_id: UUID, device_group: str) -> OtpPauseState | None:
        pause_state = await redis_json_get(otp_task_pause_key(task_id, dept_id, device_group))
        return cast(OtpPauseState, pause_state) if pause_state else None

    async def clear_pause(self, task_id: str, dept_id: UUID, device_group: str) -> None:
        await redis_delete(otp_task_pause_key(task_id, dept_id, device_group))

    async def resume_group(self, task_id: str, dept_id: UUID, device_group: str) -> OtpPauseState | None:
        pause_state = await self.get_pause(task_id, dept_id, device_group)
        await self.clear_pause(task_id, dept_id, device_group)
        await self.clear_wait_state(dept_id, device_group)
        await self.release_wait_lock(dept_id, device_group)
        return pause_state


otp_coordinator = OtpCoordinator()
