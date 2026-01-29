from typing import Any, Iterable
from uuid import UUID

from app.core.config import settings
from app.core.otp import otp_coordinator
from app.core.otp_notice import is_otp_error_text
from app.schemas.backup import OTPNotice


def _parse_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def _parse_uuid_list(values: Iterable[Any] | None) -> list[UUID] | None:
    if not values:
        return None
    parsed: list[UUID] = []
    for value in values:
        parsed_value = _parse_uuid(value)
        if parsed_value:
            parsed.append(parsed_value)
    return parsed or None


def _to_str_list(values: Iterable[Any] | None) -> list[str] | None:
    if not values:
        return None
    result = [str(value) for value in values if value is not None]
    return result or None


def _resolve_notice_message(wait_status: str | None, message: str | None) -> str:
    if message:
        return message
    if wait_status == "timeout":
        return "用户未提供 OTP 验证码，连接失败"
    return "需要重新输入 OTP 验证码"


def _resolve_notice_type(wait_status: str | None) -> str:
    return "otp_timeout" if wait_status == "timeout" else "otp_required"


def dedupe_otp_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique_groups: list[dict[str, Any]] = []
    for group in groups:
        dept_id = group.get("dept_id")
        device_group = group.get("device_group")
        key = (str(dept_id), str(device_group))
        if key in seen:
            continue
        seen.add(key)
        unique_groups.append(group)
    return unique_groups


def build_otp_required_info(
    *,
    dept_id: str | UUID | None,
    device_group: str | None,
    failed_device_ids: Iterable[Any] | None = None,
    wait_status: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    info: dict[str, Any] = {"otp_required": True}
    if dept_id is not None:
        info["otp_dept_id"] = str(dept_id)
    if device_group is not None:
        info["otp_device_group"] = str(device_group)
    if failed_device_ids is not None:
        info["otp_failed_device_ids"] = _to_str_list(failed_device_ids) or []
    if wait_status is not None:
        info["otp_wait_status"] = wait_status
    if message:
        info["message"] = message
    return info


def build_otp_required_task_result(
    groups: list[dict[str, Any]],
    *,
    next_action: str,
    wait_status: str | None = None,
    task_id: str | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(existing or {})
    payload.update(
        {
            "otp_required": True,
            "otp_required_groups": groups,
            "expires_in": settings.OTP_CACHE_TTL_SECONDS,
            "otp_wait_timeout": settings.OTP_WAIT_TIMEOUT_SECONDS,
            "otp_cache_ttl": settings.OTP_CACHE_TTL_SECONDS,
            "next_action": next_action,
        }
    )
    if wait_status is not None:
        payload["otp_wait_status"] = wait_status
    if task_id is not None:
        payload["task_id"] = task_id
    return payload


def extract_otp_failed_device_ids(results: Iterable[Any] | None) -> list[str]:
    if not results:
        return []
    failed_ids: list[str] = []
    for item in results:
        if isinstance(item, dict):
            success = item.get("success")
            error = item.get("error_message") or item.get("error")
            device_id = item.get("device_id") or item.get("id")
        else:
            success = getattr(item, "success", None)
            error = getattr(item, "error_message", None) or getattr(item, "error", None)
            device_id = getattr(item, "device_id", None) or getattr(item, "id", None)

        if success is False and is_otp_error_text(error):
            if device_id is not None:
                failed_ids.append(str(device_id))
    return failed_ids


async def should_emit_otp_notice(info: dict[str, Any], *, task_id: str, force: bool = False) -> bool:
    dept_id = info.get("otp_dept_id") or info.get("dept_id")
    device_group = info.get("otp_device_group") or info.get("device_group")
    if not dept_id or not device_group:
        return True
    if force:
        return True
    pending_ids = info.get("otp_failed_device_ids") or info.get("pending_device_ids")
    pending_strs = _to_str_list(pending_ids)
    try:
        return await otp_coordinator.should_notify_group(
            UUID(str(dept_id)),
            str(device_group),
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
    if not info or not info.get("otp_required"):
        return None
    if force:
        await should_emit_otp_notice(info, task_id=task_id)
    elif not await should_emit_otp_notice(info, task_id=task_id):
        return None

    wait_status = info.get("otp_wait_status")
    dept_id = info.get("otp_dept_id") or info.get("dept_id")
    device_group = info.get("otp_device_group") or info.get("device_group")
    pending_ids = info.get("otp_failed_device_ids") or info.get("pending_device_ids")
    notice_message = _resolve_notice_message(wait_status, message or info.get("message"))

    return OTPNotice(
        type=_resolve_notice_type(wait_status),
        message=notice_message,
        dept_id=_parse_uuid(dept_id),
        device_group=str(device_group) if device_group is not None else None,
        pending_device_ids=_parse_uuid_list(pending_ids),
        otp_wait_status=wait_status,
        otp_wait_timeout=info.get("otp_wait_timeout") or settings.OTP_WAIT_TIMEOUT_SECONDS,
        otp_cache_ttl=info.get("otp_cache_ttl") or settings.OTP_CACHE_TTL_SECONDS,
        task_id=task_id,
    )


async def record_pause_and_build_notice(
    *,
    task_id: str,
    dept_id: UUID,
    device_group: str,
    pending_device_ids: Iterable[Any] | None,
    wait_status: str | None = None,
    message: str | None = None,
    force: bool = False,
) -> OTPNotice | None:
    pending_strs = _to_str_list(pending_device_ids) or []
    await otp_coordinator.record_pause(
        task_id,
        dept_id,
        device_group,
        pending_strs,
        reason="otp_required",
    )

    info = build_otp_required_info(
        dept_id=dept_id,
        device_group=device_group,
        failed_device_ids=pending_strs,
        wait_status=wait_status,
        message=message,
    )
    info["otp_wait_timeout"] = settings.OTP_WAIT_TIMEOUT_SECONDS
    info["otp_cache_ttl"] = settings.OTP_CACHE_TTL_SECONDS

    return await build_otp_notice_from_info(info, task_id=task_id, message=message, force=force)
