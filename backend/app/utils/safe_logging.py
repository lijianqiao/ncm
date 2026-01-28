"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: safe_logging.py
@DateTime: 2026-01-28 10:00:00
@Docs: 安全日志辅助函数 - 用于在日志记录前移除或掩码敏感信息。
"""

from typing import Any

# 敏感字段关键字集合（使用 frozenset 提高查找性能）
SENSITIVE_KEYS = frozenset({
    "password",
    "auth_password",
    "auth_secondary",
    "secret",
    "token",
    "key",
    "credential",
    "otp",
    "seed",
    "private",
})


def sanitize_dict(data: dict[str, Any], mask: str = "***") -> dict[str, Any]:
    """
    移除或掩码字典中的敏感字段。

    Args:
        data: 原始字典数据
        mask: 掩码字符串（默认 "***"）

    Returns:
        处理后的字典，敏感字段值被替换为掩码
    """
    if not isinstance(data, dict):
        return data

    return {
        k: mask if _is_sensitive_key(k) else (
            sanitize_dict(v, mask) if isinstance(v, dict) else v
        )
        for k, v in data.items()
    }


def _is_sensitive_key(key: str) -> bool:
    """
    判断键名是否为敏感字段。

    Args:
        key: 键名

    Returns:
        是否为敏感字段
    """
    key_lower = key.lower()
    return any(s in key_lower for s in SENSITIVE_KEYS)


def safe_repr(obj: Any, max_length: int = 200) -> str:
    """
    安全的对象字符串表示，自动掩码敏感信息并限制长度。

    Args:
        obj: 要表示的对象
        max_length: 最大字符串长度（默认 200）

    Returns:
        安全的字符串表示
    """
    if isinstance(obj, dict):
        obj = sanitize_dict(obj)

    repr_str = repr(obj)
    if len(repr_str) > max_length:
        return repr_str[:max_length] + "..."
    return repr_str


def sanitize_for_log(data: Any, mask: str = "***") -> Any:
    """
    递归处理数据结构，掩码所有敏感信息。

    支持 dict、list、tuple 等嵌套结构。

    Args:
        data: 原始数据
        mask: 掩码字符串

    Returns:
        处理后的数据
    """
    if isinstance(data, dict):
        return sanitize_dict(data, mask)
    elif isinstance(data, list):
        return [sanitize_for_log(item, mask) for item in data]
    elif isinstance(data, tuple):
        return tuple(sanitize_for_log(item, mask) for item in data)
    else:
        return data
