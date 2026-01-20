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
