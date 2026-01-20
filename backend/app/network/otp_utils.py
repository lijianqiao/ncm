"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: otp_utils.py
@DateTime: 2026-01-20 00:55:00
@Docs: OTP 辅助工具（缓存读取与异常封装）。
"""

from uuid import UUID

from app.core.exceptions import OTPRequiredException
from app.core.otp_service import otp_service


def build_otp_required_exception(
    dept_id: UUID,
    device_group: str,
    failed_id: str,
    message: str = "需要输入 OTP 验证码",
) -> OTPRequiredException:
    return OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=[str(failed_id)],
        message=message,
    )


async def get_manual_otp_or_raise(
    dept_id: UUID,
    device_group: str,
    failed_id: str,
) -> str:
    otp_code = await otp_service.get_cached_otp(dept_id, str(device_group))
    if not otp_code:
        raise build_otp_required_exception(dept_id, str(device_group), failed_id)
    return otp_code


async def get_seed_otp(encrypted_seed: str) -> str:
    if not encrypted_seed:
        raise ValueError("缺少 OTP 种子，无法生成验证码")
    return otp_service.generate_totp(str(encrypted_seed))


async def invalidate_manual_otp(dept_id: UUID, device_group: str) -> None:
    await otp_service.invalidate_otp(dept_id, str(device_group))


async def handle_otp_auth_failure(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> str:
    """
    处理 OTP 认证失败：失效旧缓存 → 立即返回 428 让前端重新输入。

    仅适用于 auth_type == 'otp_manual' 的设备。
    立即抛出 OTPRequiredException，不阻塞等待。

    Args:
        host_data: 包含 auth_type, dept_id, device_group 等
        original_error: 原始认证错误
        failed_devices: 失败设备列表

    Raises:
        OTPRequiredException: OTP 认证失败，需要前端重新输入
        原始异常: 非 otp_manual 设备
    """
    from app.core.logger import logger

    auth_type = host_data.get("auth_type")
    if auth_type != "otp_manual":
        # 非 otp_manual 设备，直接抛出原始错误
        raise original_error

    dept_id_raw = host_data.get("dept_id")
    device_group = host_data.get("device_group")

    if not dept_id_raw or not device_group:
        raise original_error

    dept_id = UUID(str(dept_id_raw))
    device_id = host_data.get("device_id") or host_data.get("name", "unknown")

    # 1. 失效旧 OTP 缓存
    try:
        await invalidate_manual_otp(dept_id, str(device_group))
        logger.info(
            "OTP 认证失败，已失效旧缓存，立即返回 428",
            dept_id=str(dept_id),
            device_group=device_group,
            device_id=str(device_id),
        )
    except Exception as e:
        logger.warning(f"失效 OTP 缓存失败: {e}")

    # 2. 立即抛出异常，让前端重新输入 OTP
    all_failed = failed_devices or [str(device_id)]
    raise OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=all_failed,
        message="OTP 认证失败，请重新输入验证码",
    )


def handle_otp_auth_failure_sync(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> str:
    """
    同步版 OTP 认证失败处理（使用 run_async 包装）。

    用于 Nornir 同步任务中。
    """
    from app.celery.base import run_async

    return run_async(handle_otp_auth_failure(host_data, original_error, failed_devices=failed_devices))
