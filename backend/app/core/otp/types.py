"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: types.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 类型定义模块 (OTP Types).

提供 OTP 相关的类型定义和数据结构。
"""

from enum import Enum
from typing import Any, Literal, TypedDict


class OtpWaitStatus(str, Enum):
    """
    OTP 等待状态枚举。

    表示 OTP 等待的不同状态。
    """

    WAITING = "waiting"  # 等待中
    TIMEOUT = "timeout"  # 超时


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


class OtpWaitState(TypedDict, total=False):
    """
    OTP 等待状态缓存结构。

    用于在 Redis 中存储 OTP 等待状态信息。

    Attributes:
        status: 等待状态
        notified: 是否已通知
        dept_id: 部门 ID
        device_group: 设备分组
        task_id: 任务 ID（可选）
        pending_device_ids: 待处理设备 ID 列表（可选）
        message: 消息（可选）
        started_at: 开始时间戳
        expires_at: 过期时间戳
        timeout_seconds: 超时时间（秒）
    """

    status: str
    notified: bool
    dept_id: str
    device_group: str
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
        dept_id: 部门 ID
        device_group: 设备分组
        pending_device_ids: 待处理设备 ID 列表
        paused_at: 暂停时间戳
        reason: 暂停原因（可选）
        extra: 额外信息（可选）
    """

    task_id: str
    dept_id: str
    device_group: str
    pending_device_ids: list[str]
    paused_at: float
    reason: str | None
    extra: dict[str, Any] | None
