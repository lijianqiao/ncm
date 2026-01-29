"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: otp_utils.py
@DateTime: 2026-01-29 16:55:00
@Docs: OTP 认证辅助函数（不等待、不重试）。
"""

from uuid import UUID

from app.core.enums import AuthType
from app.core.exceptions import OTPRequiredException
from app.core.logger import logger
from app.core.otp import otp_coordinator
from app.core.otp_service import otp_service


def _extract_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


async def resolve_otp_password(auth_type: str | None, host_data: dict) -> str | None:
    """
    解析 OTP 密码：
    - otp_manual: 从缓存获取或抛出 OTPRequiredException
    - otp_seed: 根据种子生成验证码
    - 其他: 返回 None
    """
    if not auth_type:
        return None

    try:
        auth_enum = AuthType(auth_type)
    except Exception:
        auth_enum = AuthType.STATIC

    if auth_enum == AuthType.OTP_SEED:
        seed = host_data.get("otp_seed_encrypted")
        if seed:
            return otp_service.generate_totp(seed)
        return None

    if auth_enum != AuthType.OTP_MANUAL:
        return None

    dept_id = _extract_uuid(host_data.get("dept_id"))
    device_group = host_data.get("device_group")
    device_id = host_data.get("device_id")

    if not dept_id or not device_group:
        raise OTPRequiredException(
            dept_id=dept_id or "unknown",
            device_group=str(device_group or "unknown"),
            failed_devices=[str(device_id)] if device_id else None,
            pending_device_ids=[str(device_id)] if device_id else None,
            message="需要输入 OTP 验证码",
            otp_wait_status="waiting",
        )

    result = await otp_coordinator.get_or_require_otp(
        dept_id,
        str(device_group),
        pending_device_ids=[str(device_id)] if device_id else None,
    )
    if result["status"] == "ready" and result["otp_code"]:
        return result["otp_code"]

    message = "用户未提供 OTP 验证码，连接失败" if result["status"] == "timeout" else "需要输入 OTP 验证码"
    raise OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=[str(device_id)] if device_id else None,
        pending_device_ids=[str(device_id)] if device_id else None,
        message=message,
        otp_wait_status=result["status"],
    )


def resolve_otp_password_sync(auth_type: str | None, host_data: dict) -> str | None:
    from app.celery.base import run_async

    return run_async(resolve_otp_password(auth_type, host_data))


async def handle_otp_auth_failure(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> None:
    """
    认证失败时统一处理 OTP 逻辑：
    - 失效缓存
    - 标记等待状态
    - 抛出 OTPRequiredException
    """
    auth_type = host_data.get("auth_type")
    if auth_type != "otp_manual":
        raise original_error

    dept_id = _extract_uuid(host_data.get("dept_id"))
    device_group = host_data.get("device_group")
    device_id = host_data.get("device_id")

    if not dept_id or not device_group:
        raise OTPRequiredException(
            dept_id=dept_id or "unknown",
            device_group=str(device_group or "unknown"),
            failed_devices=failed_devices or ([str(device_id)] if device_id else None),
            pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
            message="需要输入 OTP 验证码",
            otp_wait_status="waiting",
        )

    await otp_coordinator.invalidate_otp(dept_id, str(device_group))
    await otp_coordinator.get_or_require_otp(
        dept_id,
        str(device_group),
        pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
    )
    logger.warning(
        "OTP 认证失败，等待重新输入",
        dept_id=str(dept_id),
        device_group=str(device_group),
        error=str(original_error),
    )
    raise OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=failed_devices or ([str(device_id)] if device_id else None),
        pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
        message="需要重新输入 OTP 验证码",
        otp_wait_status="waiting",
    )


def handle_otp_auth_failure_sync(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> None:
    from app.celery.base import run_async

    return run_async(handle_otp_auth_failure(host_data, original_error, failed_devices=failed_devices))
