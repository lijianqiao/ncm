"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validators.py
@DateTime: 2026-01-09 00:00:00
@Docs: 项目通用校验工具（手机号、密码强度等）。
"""

import re

import phonenumbers

from app.core.config import settings


def validate_password_strength(password: str) -> str:
    """验证密码强度。

    - 开启复杂度：大小写字母 + 数字 + 特殊字符，且长度 >= 8
    - 关闭复杂度：仅要求长度 >= 6
    """

    if settings.PASSWORD_COMPLEXITY_ENABLED:
        if len(password) < 8:
            raise ValueError("密码长度至少为 8 位")
        if not re.search(r"[a-z]", password):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"[A-Z]", password):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"\d", password):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError('密码必须包含特殊字符 (!@#$%^&*(),.?":{}|<>)')
    else:
        if len(password) < 6:
            raise ValueError("密码长度至少为 6 位")

    return password


def validate_phone_number(v: str | None, *, required: bool = False) -> str | None:
    """验证手机号格式（支持国际化，默认按中国大陆 CN 解析）。

    Args:
        v: 手机号码字符串
        required: 是否为必填字段

    Returns:
        格式化后的 E.164 格式手机号
    """

    if v is None:
        if required:
            raise ValueError("手机号不能为空")
        return None

    try:
        parsed_number = phonenumbers.parse(v, "CN")
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValueError("无效的手机号码")
        return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as e:
        raise ValueError("手机号码格式错误") from e
