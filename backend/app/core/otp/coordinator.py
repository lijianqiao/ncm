"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: coordinator.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 协调器模块 (OTP Coordinator).

统一管理 OTP 验证码的缓存、等待状态与任务暂停功能。
"""

import time
from typing import Any, cast
from uuid import UUID

from app.core.config import settings
from app.core.logger import logger

from .registry import OtpTaskRegistry
from .storage import (
    otp_cache_key_by_credential,
    otp_invalidate_lock_key,
    otp_retry_key,
    otp_task_pause_key_by_credential,
    otp_wait_lock_key_by_credential,
    otp_wait_signal_key,
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

    async def safe_invalidate_and_poll(self, credential_id: UUID) -> None:
        """
        带分布式锁的 OTP invalidate。

        用于防止多个 Celery 任务（同一 credential_id 的不同子任务）
        同时执行 invalidate_otp，避免清掉用户刚输入的新 OTP。
        只有第一个拿到锁的调用者执行 invalidate，其他调用者跳过直接进入轮询。

        Args:
            credential_id: 凭据 ID
        """
        lock_key = otp_invalidate_lock_key(credential_id)
        acquired = await redis_setnx_ex(lock_key, self.wait_timeout, "1")
        if acquired:
            await self.invalidate_otp(credential_id)
            logger.debug("OTP invalidate 已执行（获取到分布式锁）", credential_id=str(credential_id))
        else:
            logger.debug("OTP invalidate 已跳过（其他任务持有锁）", credential_id=str(credential_id))
        # 无论是否拿到锁，都不影响后续轮询

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

        locked = await self.acquire_wait_lock(credential_id)
        if not locked:
            # 其他请求已在处理，重新读取现有状态
            existing = await redis_json_get(otp_wait_state_key_by_credential(credential_id))
            if existing:
                return cast(OtpWaitState, existing)
            # 锁被占用但状态尚未写入，仍使用新状态（极端竞态下的兜底）

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
        accumulate: bool = True,
    ) -> None:
        """
        记录任务暂停状态（支持累积）。

        Args:
            task_id: 任务 ID
            credential_id: 凭据 ID
            pending_device_ids: 待处理设备 ID 列表
            reason: 暂停原因（可选）
            extra: 额外信息（可选）
            accumulate: 是否累积设备 ID，默认为 True。
                        当同一凭证的多个批次需要等待时累积所有设备。
        """
        # 如果是累积模式，读取现有的 pause_state 并合并设备 ID
        merged_device_ids: list[str] = [str(x) for x in pending_device_ids]
        if accumulate:
            existing = await self.get_pause(task_id, credential_id)
            if existing:
                existing_ids = set(existing.get("pending_device_ids") or [])
                merged_device_ids = list(existing_ids | set(merged_device_ids))

        payload: OtpPauseState = {
            "task_id": task_id,
            "credential_id": str(credential_id),
            "pending_device_ids": merged_device_ids,
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

    # ===== OTP 等待信号（通知轮询端点返回 428） =====

    async def signal_otp_wait(
        self,
        celery_task_id: str,
        credential_id: UUID,
        *,
        credential_username: str | None = None,
        credential_device_group: str | None = None,
    ) -> bool:
        """
        发出 OTP 等待信号（由 AsyncRunner 在任务内等待 OTP 时调用）。

        轮询端点检测到此信号后返回 428，通知前端弹出 OTP 输入框。
        这是一个通用机制，备份/部署/拓扑等任务均可使用。

        Args:
            celery_task_id: Celery 任务 ID
            credential_id: 凭据 ID
            credential_username: 凭据用户名（前端展示用）
            credential_device_group: 凭据设备分组（前端展示用）

        Returns:
            bool: 是否写入成功
        """
        data = {
            "credential_id": str(credential_id),
            "credential_username": credential_username,
            "credential_device_group": credential_device_group,
            "timestamp": time.time(),
        }
        return await redis_json_set(otp_wait_signal_key(celery_task_id), self.wait_timeout, data)

    async def get_otp_wait_signal(self, celery_task_id: str) -> dict[str, Any] | None:
        """
        读取 OTP 等待信号（由轮询端点调用）。

        Args:
            celery_task_id: Celery 任务 ID

        Returns:
            dict | None: 等待信号数据，包含 credential_id 等信息
        """
        return await redis_json_get(otp_wait_signal_key(celery_task_id))

    async def clear_otp_wait_signal(self, celery_task_id: str) -> None:
        """
        清除 OTP 等待信号（等待完成后调用）。

        Args:
            celery_task_id: Celery 任务 ID
        """
        await redis_delete(otp_wait_signal_key(celery_task_id))

    # ===== OTP 重试存储（执行中 OTP 过期的设备） =====

    async def record_otp_retry(
        self,
        batch_id: str,
        credential_id: UUID,
        device_ids: list[str],
        *,
        credential_username: str | None = None,
        credential_device_group: str | None = None,
    ) -> bool:
        """
        记录 OTP 过期失败的设备到重试存储（由 Celery 任务调用）。

        同一 credential 的多次写入自动合并（set union），确保所有子任务的
        OTP 失败设备被完整收集。

        Args:
            batch_id: 批次 ID
            credential_id: 凭据 ID
            device_ids: 设备 ID 列表
            credential_username: 凭据用户名（用于前端展示）
            credential_device_group: 凭据设备分组（用于前端展示）

        Returns:
            bool: 是否写入成功
        """
        key = otp_retry_key(batch_id)
        existing = await redis_json_get(key) or {}
        cred_str = str(credential_id)
        group = existing.get(cred_str) or {"device_ids": [], "username": None, "device_group": None}
        merged_ids = set(group.get("device_ids") or [])
        merged_ids.update(str(x) for x in device_ids if x)
        group["device_ids"] = sorted(merged_ids)
        if credential_username:
            group["username"] = credential_username
        if credential_device_group:
            group["device_group"] = credential_device_group
        existing[cred_str] = group
        ok = await redis_json_set(key, 3600, existing)
        if ok:
            logger.info(
                "OTP 重试设备已记录",
                batch_id=batch_id,
                credential_id=cred_str,
                device_count=len(group["device_ids"]),
            )
        return ok

    async def get_otp_retries(self, batch_id: str) -> dict[str, Any] | None:
        """
        获取批次的所有 OTP 重试设备（按 credential_id 分组）。

        Args:
            batch_id: 批次 ID

        Returns:
            dict | None: {credential_id: {device_ids: [...], username: ..., device_group: ...}}
        """
        return await redis_json_get(otp_retry_key(batch_id))

    async def clear_otp_retry(self, batch_id: str, credential_id: UUID) -> None:
        """
        清除指定凭证的 OTP 重试记录（恢复后调用）。

        如果该批次下还有其他凭证的重试记录则保留，全部清空则删除整个 key。

        Args:
            batch_id: 批次 ID
            credential_id: 凭据 ID
        """
        key = otp_retry_key(batch_id)
        existing = await redis_json_get(key)
        if not existing:
            return
        existing.pop(str(credential_id), None)
        if existing:
            await redis_json_set(key, 3600, existing)
        else:
            await redis_delete(key)

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
