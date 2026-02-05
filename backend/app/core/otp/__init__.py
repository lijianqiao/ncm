"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 模块 (OTP Module).

提供 OTP 验证码的协调、注册、存储、类型定义、通知构建和 HTTP 响应构建。
"""

from .coordinator import OtpCoordinator, otp_coordinator
from .meta import OtpMetaBuilder
from .notice import (
    build_otp_notice_from_info,
    build_otp_notice_from_meta,
    record_pause_and_build_notice,
    should_emit_otp_notice,
)
from .registry import OtpTaskRegistry
from .response import (
    build_otp_notice_response,
    build_otp_required_response,
    build_otp_required_response_for_failed_devices,
    build_otp_required_response_from_result,
    build_otp_timeout_response,
)
from .result_parser import OtpResultParser
from .types import OtpAcquireResult, OtpMeta, OtpPauseState, OtpWaitState, OtpWaitStatus
from .utils import (
    dedupe_otp_groups,
    extract_otp_failed_device_ids,
    is_otp_error_text,
    normalize_otp_group,
    parse_uuid,
    parse_uuid_list,
    to_str_list,
)

__all__ = [
    # 协调器
    "OtpCoordinator",
    "otp_coordinator",
    # 注册表
    "OtpTaskRegistry",
    # 类型定义
    "OtpMeta",
    "OtpAcquireResult",
    "OtpPauseState",
    "OtpWaitState",
    "OtpWaitStatus",
    # 构建器与解析器
    "OtpMetaBuilder",
    "OtpResultParser",
    # HTTP 响应构建
    "build_otp_required_response",
    "build_otp_timeout_response",
    "build_otp_required_response_from_result",
    "build_otp_notice_response",
    "build_otp_required_response_for_failed_devices",
    # 通知构建
    "build_otp_notice_from_meta",
    "build_otp_notice_from_info",
    "should_emit_otp_notice",
    "record_pause_and_build_notice",
    # 工具函数
    "parse_uuid",
    "parse_uuid_list",
    "to_str_list",
    "is_otp_error_text",
    "dedupe_otp_groups",
    "normalize_otp_group",
    "extract_otp_failed_device_ids",
]
