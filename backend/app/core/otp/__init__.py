"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 模块 (OTP Module).

提供 OTP 验证码的协调、注册、存储和类型定义。
"""

from .coordinator import OtpCoordinator, otp_coordinator
from .registry import OtpTaskRegistry
from .types import OtpAcquireResult, OtpPauseState, OtpWaitState, OtpWaitStatus

__all__ = [
    "OtpCoordinator",
    "OtpTaskRegistry",
    "OtpAcquireResult",
    "OtpPauseState",
    "OtpWaitState",
    "OtpWaitStatus",
    "otp_coordinator",
]
