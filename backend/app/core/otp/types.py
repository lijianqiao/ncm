"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: types.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 类型定义模块 (OTP Types).

提供 OTP 相关的类型定义和数据结构。
"""

from enum import StrEnum
from typing import Any, Literal, TypedDict


class OtpWaitStatus(StrEnum):
    """
    OTP 等待状态枚举。

    表示 OTP 等待的不同状态。
    """

    WAITING = "waiting"  # 等待中
    TIMEOUT = "timeout"  # 超时
    READY = "ready"  # 已就绪


class OtpAcquireResult(TypedDict):
    """
    OTP 获取结果类型。

    表示获取 OTP 验证码的结果。

    Attributes:
        status: 状态（ready/waiting/timeout）
        otp_code: OTP 验证码（如果已准备好）
        should_notify: 是否应该通知用户
    """

    status: Literal["ready", "waiting", "timeout"]
    otp_code: str | None
    should_notify: bool


class OtpMeta(TypedDict, total=False):
    """
    统一 OTP 元数据结构。

    用于在各层之间传递 OTP 相关信息，提供统一的数据格式。
    业务层/任务层只需提供最小上下文，由 OtpMetaBuilder 构建完整结构。

    Attributes:
        otp_required: 是否需要 OTP 验证
        otp_credential_id: 凭据 ID
        otp_credential_username: 凭据用户名
        otp_credential_device_group: 凭据设备分组
        otp_wait_status: 等待状态 (waiting/timeout/ready)
        otp_failed_device_ids: 失败设备 ID 列表
        pending_device_ids: 待处理设备 ID 列表
        task_id: 关联任务 ID
        otp_wait_timeout: 等待超时时间（秒）
        otp_cache_ttl: 缓存 TTL（秒）
        message: 提示消息
    """

    otp_required: bool
    otp_credential_id: str | None
    otp_credential_username: str | None
    otp_credential_device_group: str | None
    otp_wait_status: str | None
    otp_failed_device_ids: list[str]
    pending_device_ids: list[str] | None
    task_id: str | None
    otp_wait_timeout: int
    otp_cache_ttl: int
    message: str | None


class OtpWaitState(TypedDict, total=False):
    """
    OTP 等待状态缓存结构。

    用于在 Redis 中存储 OTP 等待状态信息。

    Attributes:
        status: 等待状态
        notified: 是否已通知
        credential_id: 凭据 ID
        task_id: 任务 ID（可选）
        pending_device_ids: 待处理设备 ID 列表（可选）
        message: 消息（可选）
        started_at: 开始时间戳
        expires_at: 过期时间戳
        timeout_seconds: 超时时间（秒）
    """

    status: str
    notified: bool
    credential_id: str | None
    task_id: str | None
    pending_device_ids: list[str] | None
    message: str | None
    started_at: float
    expires_at: float
    timeout_seconds: int


class OtpPauseState(TypedDict, total=False):
    """
    OTP 暂停状态结构。

    用于记录任务因等待 OTP 而暂停的状态信息。

    Attributes:
        task_id: 任务 ID
        credential_id: 凭据 ID
        pending_device_ids: 待处理设备 ID 列表
        paused_at: 暂停时间戳
        reason: 暂停原因（可选）
        extra: 额外信息（可选）
    """

    task_id: str
    credential_id: str | None
    pending_device_ids: list[str]
    paused_at: float
    reason: str | None
    extra: dict[str, Any] | None
