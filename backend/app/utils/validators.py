"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: validators.py
@DateTime: 2026-01-09 00:00:00
@Docs: 项目通用校验工具（手机号、密码强度、IP/MAC地址等）。
"""

import re

import phonenumbers
from netaddr import EUI, AddrFormatError, IPAddress, mac_unix_expanded

from app.core.config import settings


def validate_ip_address(ip: str) -> str:
    """验证 IP 地址格式（支持 IPv4/IPv6）。

    使用 netaddr 库进行校验，支持多种格式。

    Args:
        ip: IP 地址字符串

    Returns:
        标准化后的 IP 地址

    Raises:
        ValueError: IP 地址格式无效
    """
    try:
        addr = IPAddress(ip)
        return str(addr)
    except AddrFormatError as e:
        raise ValueError(f"无效的 IP 地址格式: {ip}") from e


def validate_mac_address(mac: str, *, normalize: bool = True) -> str:
    """验证 MAC 地址格式。

    使用 netaddr 库进行校验，支持多种格式：
    - 00:11:22:33:44:55 (冒号分隔)
    - 00-11-22-33-44-55 (短横线分隔)
    - 0011.2233.4455 (思科格式)
    - 0011-2233-4455 (华为格式)
    - 001122334455 (无分隔符)

    Args:
        mac: MAC 地址字符串
        normalize: 是否标准化为大写冒号分隔格式

    Returns:
        标准化后的 MAC 地址（大写，冒号分隔）

    Raises:
        ValueError: MAC 地址格式无效
    """
    try:
        eui = EUI(mac)
        if normalize:
            # 设置为 unix_expanded 格式（冒号分隔，完整字节）然后转大写
            eui.dialect = mac_unix_expanded
            return str(eui).upper()
        return mac.upper()
    except AddrFormatError as e:
        raise ValueError(f"无效的 MAC 地址格式: {mac}") from e


def validate_cidr(cidr: str) -> str:
    """验证 CIDR 网段格式。

    Args:
        cidr: CIDR 格式网段（如 192.168.1.0/24）

    Returns:
        标准化后的 CIDR 字符串

    Raises:
        ValueError: CIDR 格式无效
    """
    from netaddr import IPNetwork

    try:
        network = IPNetwork(cidr)
        return str(network.cidr)
    except AddrFormatError as e:
        raise ValueError(f"无效的 CIDR 格式: {cidr}") from e


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
