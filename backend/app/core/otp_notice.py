"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: otp_notice.py
@DateTime: 2026-01-20 10:00:00
@Docs: OTP 认证失败提示组件。
"""

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.exceptions import OTPRequiredException


def build_otp_required_details(
    exc: OTPRequiredException | None = None,
    *,
    message: str | None = None,
    dept_id: str | None = None,
    device_group: str | None = None,
    failed_devices: list[str] | None = None,
) -> dict[str, Any]:
    """
    构建 OTP 认证失败的统一详情结构。
    """
    details: dict[str, Any] = {"otp_required": True}

    if exc and exc.details:
        details.update(exc.details)

    if dept_id:
        details["dept_id"] = str(dept_id)
    if device_group:
        details["device_group"] = str(device_group)
    if failed_devices is not None:
        details["failed_devices"] = [str(x) for x in failed_devices]

    if message:
        details["message"] = message

    return details


def is_otp_error_text(text: str | None) -> bool:
    """
    判断错误文本是否为 OTP 认证失败。
    """
    if not text:
        return False
    lowered = text.lower()
    return "otp" in lowered and ("过期" in lowered or "required" in lowered or "认证" in lowered or "验证码" in lowered)


def build_otp_required_response(
    exc: OTPRequiredException | None = None,
    *,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """
    构建 OTP 认证失败的统一响应（HTTP 428）。

    返回格式与 ResponseBase 保持一致。
    """
    if exc is not None and message is None:
        message = exc.message

    resolved_message = message or "需要重新输入 OTP 验证码"
    resolved_details = details or build_otp_required_details(exc, message=resolved_message)

    payload = {
        "code": 428,
        "message": resolved_message,
        "data": resolved_details,
    }

    return JSONResponse(status_code=428, content=jsonable_encoder(payload))
