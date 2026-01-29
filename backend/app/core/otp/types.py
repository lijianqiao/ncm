from enum import Enum
from typing import Any, Literal, TypedDict


class OtpWaitStatus(str, Enum):
    """OTP 等待状态。"""

    WAITING = "waiting"
    TIMEOUT = "timeout"


class OtpAcquireResult(TypedDict):
    """OTP 获取结果。"""

    status: Literal["ready", "waiting", "timeout"]
    otp_code: str | None
    should_notify: bool


class OtpWaitState(TypedDict, total=False):
    """OTP 等待状态缓存结构。"""

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
    """OTP 暂停状态结构。"""

    task_id: str
    dept_id: str
    device_group: str
    pending_device_ids: list[str]
    paused_at: float
    reason: str | None
    extra: dict[str, Any] | None
