"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: utils.py
@DateTime: 2026-02-05 15:00:00
@Docs: OTP 工具函数模块。

提供 OTP 相关的通用工具函数，包括 UUID 解析、列表转换、文本判断等。
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID


def parse_uuid(value: Any) -> UUID | None:
    """解析 UUID。

    Args:
        value: 可能包含 UUID 的值

    Returns:
        UUID | None: 解析成功的 UUID，失败返回 None
    """
    if isinstance(value, UUID):
        return value
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def parse_uuid_list(values: Iterable[Any] | None) -> list[UUID] | None:
    """解析 UUID 列表。

    Args:
        values: 可能包含 UUID 的值列表

    Returns:
        list[UUID] | None: 解析成功的 UUID 列表，空则返回 None
    """
    if not values:
        return None
    parsed: list[UUID] = []
    for value in values:
        parsed_value = parse_uuid(value)
        if parsed_value:
            parsed.append(parsed_value)
    return parsed or None


def to_str_list(values: Iterable[Any] | None) -> list[str] | None:
    """将可迭代对象转换为字符串列表。

    Args:
        values: 可迭代对象

    Returns:
        list[str] | None: 字符串列表，空则返回 None
    """
    if not values:
        return None
    result = [str(value) for value in values if value is not None]
    return result or None


def is_otp_error_text(text: str | None) -> bool:
    """判断错误文本是否为 OTP 认证失败。

    匹配的错误文本示例：
    - "OTP 多次重试仍然失败"
    - "等待 OTP 验证码超时"
    - "需要重新输入 OTP 验证码"
    - "OTP 过期"
    - "OTP_REQUIRED"
    - "OTP 处理异常: ..."

    Args:
        text: 错误文本

    Returns:
        bool: 是否为 OTP 相关错误
    """
    if not text:
        return False
    lowered = text.lower()
    if "otp" not in lowered:
        return False
    _OTP_KEYWORDS = ("过期", "required", "认证", "验证码", "重试", "失败", "超时", "处理异常")
    return any(kw in lowered for kw in _OTP_KEYWORDS)


def dedupe_otp_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去重 OTP 分组列表（基于 credential_id 或 otp_credential_id）。

    兼容新旧格式：
    - 旧格式使用 `credential_id` 字段
    - 新格式（OtpMeta）使用 `otp_credential_id` 字段

    Args:
        groups: OTP 分组列表

    Returns:
        list[dict[str, Any]]: 去重后的分组列表
    """
    seen: set[str] = set()
    unique_groups: list[dict[str, Any]] = []
    for group in groups:
        # 兼容新旧字段名
        credential_id = group.get("otp_credential_id") or group.get("credential_id")
        key = str(credential_id)
        if key in seen:
            continue
        seen.add(key)
        unique_groups.append(group)
    return unique_groups


def normalize_otp_group(group: dict[str, Any]) -> dict[str, Any]:
    """标准化 OTP 分组字典，确保同时包含新旧字段名。

    用于兼容前端可能使用的旧字段名（credential_id）和新字段名（otp_credential_id）。

    Args:
        group: OTP 分组字典（可能是 OtpMeta 格式或旧格式）

    Returns:
        dict[str, Any]: 标准化后的字典，同时包含新旧字段名
    """
    result = dict(group)
    # 确保同时包含 credential_id 和 otp_credential_id
    cred_id = group.get("otp_credential_id") or group.get("credential_id")
    if cred_id:
        result["credential_id"] = str(cred_id)
        result["otp_credential_id"] = str(cred_id)
    return result


def extract_otp_failed_device_ids(results: Iterable[Any] | None) -> list[str]:
    """从结果中提取 OTP 认证失败的设备 ID 列表。

    Args:
        results: 结果列表（字典或对象）

    Returns:
        list[str]: 失败设备 ID 列表
    """
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


def resolve_notice_message(wait_status: str | None, message: str | None) -> str:
    """根据等待状态解析通知消息。

    Args:
        wait_status: 等待状态
        message: 原始消息

    Returns:
        str: 解析后的消息
    """
    if message:
        return message
    if wait_status == "timeout":
        return "用户未提供 OTP 验证码，连接失败"
    return "需要重新输入 OTP 验证码"


def resolve_notice_type(wait_status: str | None) -> str:
    """根据等待状态解析通知类型。

    Args:
        wait_status: 等待状态

    Returns:
        str: 通知类型（otp_timeout 或 otp_required）
    """
    return "otp_timeout" if wait_status == "timeout" else "otp_required"
