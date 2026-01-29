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

from app.core.config import settings
from app.core.exceptions import OTPRequiredException


def build_otp_required_details(
    exc: OTPRequiredException | None = None,
    *,
    message: str | None = None,
    dept_id: str | None = None,
    device_group: str | None = None,
    failed_devices: list[str] | None = None,
    pending_device_ids: list[str] | None = None,
    task_id: str | None = None,
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
    if pending_device_ids is not None:
        details["pending_device_ids"] = [str(x) for x in pending_device_ids]
    if task_id:
        details["task_id"] = task_id

    if message:
        details["message"] = message

    if "otp_wait_timeout" not in details:
        details["otp_wait_timeout"] = settings.OTP_WAIT_TIMEOUT_SECONDS
    if "otp_cache_ttl" not in details:
        details["otp_cache_ttl"] = settings.OTP_CACHE_TTL_SECONDS

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


def build_otp_timeout_response(
    result: dict[str, Any] | None,
    *,
    message: str | None = None,
) -> JSONResponse | None:
    """
    从任务结果中构造 OTP 超时响应（HTTP 428）。

    用于复用 otp_timeout 的返回结构，避免在接口中重复拼装。
    """
    if not result or not isinstance(result, dict):
        return None
    wait_status = result.get("otp_wait_status")
    if wait_status != "timeout" and not result.get("otp_timeout"):
        return None
    dept_id = result.get("dept_id") or result.get("otp_dept_id")
    device_group = result.get("device_group") or result.get("otp_device_group")
    if not dept_id or not device_group:
        return None
    return build_otp_required_response(
        message=message or "用户未提供 OTP 验证码，连接失败",
        details={
            "otp_required": True,
            "dept_id": dept_id,
            "device_group": device_group,
            "otp_wait_status": "timeout",
            "pending_device_ids": result.get("pending_device_ids"),
            "task_id": result.get("task_id"),
            "otp_wait_timeout": result.get("otp_wait_timeout"),
            "otp_cache_ttl": result.get("otp_cache_ttl"),
        },
    )


def build_otp_required_response_from_result(
    result: dict[str, Any] | None,
    *,
    message: str | None = None,
) -> JSONResponse | None:
    """
    从任务结果中构造 OTP_REQUIRED 响应（HTTP 428）。

    适用于 result 中包含 otp_required/otp_required_groups 等字段的场景。
    """
    if not result or not isinstance(result, dict):
        return None
    if not result.get("otp_required"):
        return None

    return build_otp_required_response(
        message=message or "需要重新输入 OTP 验证码",
        details={
            "otp_required": True,
            "dept_id": result.get("dept_id") or result.get("otp_dept_id"),
            "device_group": result.get("device_group") or result.get("otp_device_group"),
            "pending_device_ids": result.get("pending_device_ids"),
            "task_id": result.get("task_id"),
            "otp_wait_status": result.get("otp_wait_status"),
            "otp_wait_timeout": result.get("otp_wait_timeout"),
            "otp_cache_ttl": result.get("otp_cache_ttl"),
        },
    )


def build_otp_notice_response(
    data: Any,
    *,
    message: str = "OTP_REQUIRED",
) -> JSONResponse:
    """
    构建带 otp_notice 的统一响应（HTTP 428）。

    用于返回任务状态中包含 otp_notice 的场景（如备份任务轮询）。
    """
    payload = {
        "code": 428,
        "message": message,
        "data": data,
    }
    return JSONResponse(status_code=428, content=jsonable_encoder(payload))


def build_otp_required_response_for_failed_devices(
    failed_devices: list[str],
    *,
    message: str | None = None,
) -> JSONResponse:
    """
    构建包含失败设备列表的 OTP_REQUIRED 响应（HTTP 428）。
    """
    return build_otp_required_response(
        message=message,
        details={"otp_required": True, "failed_devices": failed_devices},
    )
