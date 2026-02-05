"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: notice.py
@DateTime: 2026-02-05 15:00:00
@Docs: OTPNotice 构建模块。

提供 OTPNotice 对象的构建函数，用于任务状态通知。
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.schemas.backup import OTPNotice

from .coordinator import otp_coordinator
from .meta import OtpMetaBuilder
from .types import OtpMeta
from .utils import parse_uuid, parse_uuid_list, resolve_notice_message, resolve_notice_type, to_str_list


def build_otp_notice_from_meta(
    meta: OtpMeta,
    *,
    task_id: str,
    message: str | None = None,
) -> OTPNotice:
    """从 OtpMeta 构建 OTPNotice。

    Args:
        meta: OTP 元数据
        task_id: 任务 ID
        message: 覆盖消息（可选）

    Returns:
        OTPNotice: 通知对象
    """
    wait_status = meta.get("otp_wait_status")
    notice_message = resolve_notice_message(wait_status, message or meta.get("message"))
    failed_device_ids = meta.get("otp_failed_device_ids") or []
    pending_ids = failed_device_ids or meta.get("pending_device_ids")

    return OTPNotice(
        type=resolve_notice_type(wait_status),
        message=notice_message,
        otp_credential_id=parse_uuid(meta.get("otp_credential_id")),
        otp_credential_username=meta.get("otp_credential_username"),
        otp_credential_device_group=meta.get("otp_credential_device_group"),
        otp_failed_device_ids=to_str_list(failed_device_ids) if failed_device_ids else None,
        pending_device_ids=parse_uuid_list(pending_ids),
        otp_wait_status=wait_status,
        otp_wait_timeout=meta.get("otp_wait_timeout") or settings.OTP_WAIT_TIMEOUT_SECONDS,
        otp_cache_ttl=meta.get("otp_cache_ttl") or settings.OTP_CACHE_TTL_SECONDS,
        task_id=task_id,
    )


async def should_emit_otp_notice(
    info: dict[str, Any],
    *,
    task_id: str,
    force: bool = False,
) -> bool:
    """判断是否应该发送 OTP 通知。

    用于避免同一凭证组重复发送通知。

    Args:
        info: OTP 信息字典
        task_id: 任务 ID
        force: 是否强制发送

    Returns:
        bool: 是否应该发送通知
    """
    credential_id = info.get("otp_credential_id") or info.get("credential_id")
    if not credential_id:
        return True
    if force:
        return True
    pending_ids = info.get("otp_failed_device_ids") or info.get("pending_device_ids")
    pending_strs = to_str_list(pending_ids)
    try:
        return await otp_coordinator.should_notify_group(
            UUID(str(credential_id)),
            task_id=task_id,
            pending_device_ids=pending_strs,
        )
    except Exception:
        return True


async def build_otp_notice_from_info(
    info: dict[str, Any],
    *,
    task_id: str,
    message: str | None = None,
    force: bool = False,
) -> OTPNotice | None:
    """从信息字典构建 OTPNotice。

    Args:
        info: OTP 信息字典
        task_id: 任务 ID
        message: 覆盖消息（可选）
        force: 是否强制发送通知

    Returns:
        OTPNotice | None: 通知对象，如果不需要发送则返回 None
    """
    if not info or not info.get("otp_required"):
        return None
    if force:
        await should_emit_otp_notice(info, task_id=task_id)
    elif not await should_emit_otp_notice(info, task_id=task_id):
        return None

    # 从 info 构建 OtpMeta
    meta = OtpMetaBuilder.from_result(info)
    if meta is None:
        # 尝试直接构建
        meta = OtpMetaBuilder.build(
            credential_id=info.get("otp_credential_id") or info.get("credential_id"),
            wait_status=info.get("otp_wait_status"),
            failed_device_ids=info.get("otp_failed_device_ids"),
            pending_device_ids=info.get("pending_device_ids"),
            credential_username=info.get("otp_credential_username"),
            credential_device_group=info.get("otp_credential_device_group"),
            message=info.get("message"),
            otp_wait_timeout=info.get("otp_wait_timeout"),
            otp_cache_ttl=info.get("otp_cache_ttl"),
        )

    return build_otp_notice_from_meta(meta, task_id=task_id, message=message)


async def record_pause_and_build_notice(
    *,
    task_id: str,
    credential_id: UUID,
    pending_device_ids: Iterable[Any] | None,
    wait_status: str | None = None,
    message: str | None = None,
    credential_username: str | None = None,
    credential_device_group: str | None = None,
    force: bool = False,
) -> OTPNotice | None:
    """记录暂停状态并构建 OTPNotice。

    Args:
        task_id: 任务 ID
        credential_id: 凭据 ID
        pending_device_ids: 待处理设备 ID 列表
        wait_status: 等待状态（可选）
        message: 消息（可选）
        credential_username: 凭据用户名（可选）
        credential_device_group: 凭据设备分组（可选）
        force: 是否强制发送通知

    Returns:
        OTPNotice | None: 通知对象
    """
    pending_strs = to_str_list(pending_device_ids) or []
    await otp_coordinator.record_pause(
        task_id,
        credential_id,
        pending_strs,
        reason="otp_required",
    )

    meta = OtpMetaBuilder.build(
        credential_id=credential_id,
        failed_device_ids=pending_strs,
        wait_status=wait_status,
        message=message,
        credential_username=credential_username,
        credential_device_group=credential_device_group,
    )
    info = OtpMetaBuilder.serialize(meta)

    return await build_otp_notice_from_info(info, task_id=task_id, message=message, force=force)
