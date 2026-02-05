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
    """从字符串中提取 UUID。

    Args:
        value: 可能包含 UUID 的字符串

    Returns:
        UUID | None: 解析成功的 UUID，失败返回 None
    """
    if not value:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


async def resolve_otp_password(auth_type: str | None, host_data: dict) -> str | None:
    """解析 OTP 密码。

    根据认证类型解析 OTP 密码：
    - otp_manual: 从缓存获取或抛出 OTPRequiredException
    - otp_seed: 根据种子生成验证码
    - 其他: 返回 None

    Args:
        auth_type: 认证类型（otp_manual, otp_seed 等）
        host_data: 主机数据字典，需包含 dept_id, device_group, device_id, otp_seed_encrypted 等

    Returns:
        str | None: OTP 密码，无需 OTP 时返回 None

    Raises:
        OTPRequiredException: OTP 手动输入模式下需要用户输入时抛出
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

    credential_id = _extract_uuid(host_data.get("credential_id"))
    device_id = host_data.get("device_id")
    credential_username = host_data.get("credential_username")
    credential_device_group = host_data.get("credential_device_group")

    if not credential_id:
        raise OTPRequiredException(
            credential_id=None,
            failed_devices=[str(device_id)] if device_id else None,
            pending_device_ids=[str(device_id)] if device_id else None,
            message="需要输入 OTP 验证码",
            otp_wait_status="waiting",
            credential_username=credential_username,
            credential_device_group=credential_device_group,
        )

    result = await otp_coordinator.get_or_require_otp(
        credential_id,
        pending_device_ids=[str(device_id)] if device_id else None,
    )
    if result["status"] == "ready" and result["otp_code"]:
        return result["otp_code"]

    message = "用户未提供 OTP 验证码，连接失败" if result["status"] == "timeout" else "需要输入 OTP 验证码"
    raise OTPRequiredException(
        credential_id=credential_id,
        failed_devices=[str(device_id)] if device_id else None,
        pending_device_ids=[str(device_id)] if device_id else None,
        message=message,
        otp_wait_status=result["status"],
        credential_username=credential_username,
        credential_device_group=credential_device_group,
    )


def resolve_otp_password_sync(auth_type: str | None, host_data: dict) -> str | None:
    """同步版本的 OTP 密码解析（用于同步上下文）。

    Args:
        auth_type: 认证类型
        host_data: 主机数据字典

    Returns:
        str | None: OTP 密码，无需 OTP 时返回 None

    Raises:
        OTPRequiredException: OTP 手动输入模式下需要用户输入时抛出
    """
    from app.celery.base import run_async

    return run_async(resolve_otp_password(auth_type, host_data))


async def handle_otp_auth_failure(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> None:
    """认证失败时统一处理 OTP 逻辑。

    处理流程：
    - 失效缓存
    - 标记等待状态
    - 抛出 OTPRequiredException

    Args:
        host_data: 主机数据字典，需包含 auth_type, dept_id, device_group, device_id
        original_error: 原始认证异常
        failed_devices: 失败设备 ID 列表（可选）

    Raises:
        OTPRequiredException: 需要重新输入 OTP 时抛出
        Exception: 非 OTP 认证类型时直接抛出原始异常
    """
    auth_type = host_data.get("auth_type")
    if auth_type != "otp_manual":
        raise original_error

    credential_id = _extract_uuid(host_data.get("credential_id"))
    device_id = host_data.get("device_id")
    credential_username = host_data.get("credential_username")
    credential_device_group = host_data.get("credential_device_group")

    if not credential_id:
        raise OTPRequiredException(
            credential_id=None,
            failed_devices=failed_devices or ([str(device_id)] if device_id else None),
            pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
            message="需要输入 OTP 验证码",
            otp_wait_status="waiting",
            credential_username=credential_username,
            credential_device_group=credential_device_group,
        )

    await otp_coordinator.invalidate_otp(
        credential_id
    )
    await otp_coordinator.get_or_require_otp(
        credential_id,
        pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
    )
    logger.warning(
        "OTP 认证失败，等待重新输入",
        credential_id=str(credential_id),
        error=str(original_error),
    )
    raise OTPRequiredException(
        credential_id=credential_id,
        failed_devices=failed_devices or ([str(device_id)] if device_id else None),
        pending_device_ids=failed_devices or ([str(device_id)] if device_id else None),
        message="需要重新输入 OTP 验证码",
        otp_wait_status="waiting",
        credential_username=credential_username,
        credential_device_group=credential_device_group,
    )


def handle_otp_auth_failure_sync(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> None:
    """同步版本的 OTP 认证失败处理（用于同步上下文）。

    Args:
        host_data: 主机数据字典
        original_error: 原始认证异常
        failed_devices: 失败设备 ID 列表（可选）

    Raises:
        OTPRequiredException: 需要重新输入 OTP 时抛出
        Exception: 非 OTP 认证类型时直接抛出原始异常
    """
    from app.celery.base import run_async

    return run_async(handle_otp_auth_failure(host_data, original_error, failed_devices=failed_devices))
