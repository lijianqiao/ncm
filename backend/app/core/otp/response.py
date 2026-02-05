"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: response.py
@DateTime: 2026-02-05 15:00:00
@Docs: OTP HTTP 响应构建模块。

提供 OTP 相关的 HTTP 响应构建函数，统一返回 428 状态码。
"""

from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .meta import OtpMetaBuilder

if TYPE_CHECKING:
    from app.core.exceptions import OTPRequiredException


def build_otp_required_response(
    exc: "OTPRequiredException | None" = None,
    *,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """构建 OTP 认证失败的统一响应（HTTP 428）。

    返回格式与 ResponseBase 保持一致。

    Args:
        exc: OTPRequiredException 异常（可选）
        message: 错误消息（可选）
        details: 详情字典（可选）

    Returns:
        JSONResponse: HTTP 428 响应
    """
    if exc is not None and message is None:
        message = exc.message

    resolved_message = message or "需要重新输入 OTP 验证码"

    if details is None and exc is not None:
        meta = OtpMetaBuilder.from_exception(exc)
        details = OtpMetaBuilder.serialize(meta)

    payload = {
        "code": 428,
        "message": resolved_message,
        "data": details or {},
    }

    return JSONResponse(status_code=428, content=jsonable_encoder(payload))


def build_otp_timeout_response(
    result: dict[str, Any] | None,
    *,
    message: str | None = None,
) -> JSONResponse | None:
    """从任务结果中构造 OTP 超时响应（HTTP 428）。

    用于复用 otp_timeout 的返回结构，避免在接口中重复拼装。

    Args:
        result: 任务结果字典
        message: 错误消息（可选）

    Returns:
        JSONResponse | None: HTTP 428 响应，如果不是超时状态则返回 None
    """
    if not result or not isinstance(result, dict):
        return None
    wait_status = result.get("otp_wait_status")
    if wait_status != "timeout" and not result.get("otp_timeout"):
        return None
    credential_id = result.get("credential_id") or result.get("otp_credential_id")
    if not credential_id:
        return None

    meta = OtpMetaBuilder.build(
        credential_id=credential_id,
        credential_username=result.get("otp_credential_username"),
        credential_device_group=result.get("otp_credential_device_group"),
        wait_status="timeout",
        pending_device_ids=result.get("pending_device_ids"),
        task_id=result.get("task_id"),
        otp_wait_timeout=result.get("otp_wait_timeout"),
        otp_cache_ttl=result.get("otp_cache_ttl"),
    )
    return build_otp_required_response(
        message=message or "用户未提供 OTP 验证码，连接失败",
        details=OtpMetaBuilder.serialize(meta),
    )


def build_otp_required_response_from_result(
    result: dict[str, Any] | None,
    *,
    message: str | None = None,
) -> JSONResponse | None:
    """从任务结果中构造 OTP_REQUIRED 响应（HTTP 428）。

    适用于 result 中包含 otp_required/otp_credentials 字段的场景。

    Args:
        result: 任务结果字典
        message: 错误消息（可选）

    Returns:
        JSONResponse | None: HTTP 428 响应，如果不需要 OTP 则返回 None
    """
    if not result or not isinstance(result, dict):
        return None
    if not result.get("otp_required"):
        return None

    meta = OtpMetaBuilder.from_result(result)
    if meta is None:
        return None

    return build_otp_required_response(
        message=message or "需要重新输入 OTP 验证码",
        details=OtpMetaBuilder.serialize(meta),
    )


def build_otp_notice_response(
    data: Any,
    *,
    message: str = "OTP_REQUIRED",
) -> JSONResponse:
    """构建带 otp_notice 的统一响应（HTTP 428）。

    用于返回任务状态中包含 otp_notice 的场景（如备份任务轮询）。

    Args:
        data: 响应数据
        message: 错误消息

    Returns:
        JSONResponse: HTTP 428 响应
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
    """构建包含失败设备列表的 OTP_REQUIRED 响应（HTTP 428）。

    Args:
        failed_devices: 失败设备 ID 列表
        message: 错误消息（可选）

    Returns:
        JSONResponse: HTTP 428 响应
    """
    return build_otp_required_response(
        message=message,
        details={"otp_required": True, "failed_devices": failed_devices},
    )
