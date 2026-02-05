"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: task_grouping.py
@DateTime: 2026-01-29 23:10:00
@Docs: Celery 批量任务分组与拆分工具。
"""

from enum import Enum
from typing import Any
from uuid import UUID

from app.core.enums import AuthType
from app.core.exceptions import BadRequestException
from app.models.device import Device


def _normalize_device_group(value: str | Enum | None) -> str | None:
    """标准化设备分组值。

    将设备分组值转换为字符串格式，处理 Enum 类型和带前缀的字符串。

    Args:
        value (str | Enum | None): 设备分组值，可以是字符串、枚举或 None。

    Returns:
        str | None: 标准化后的字符串，如果输入为 None 则返回 None。
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    text = str(value)
    if text.startswith("DeviceGroup."):
        text = text.split(".", maxsplit=1)[-1]
    return text


def build_backup_batches(devices: list[Device], *, chunk_size: int = 50) -> list[dict[str, Any]]:
    """
    批量备份分组规则：
    - static：不按凭据分组，按 50 台分批
    - otp_seed/otp_manual：按 credential_id 分组后再按 50 台分批

    Args:
        devices (list[Device]): 设备列表。
        chunk_size (int): 每批设备数量，默认为 50。

    Returns:
        list[dict[str, Any]]: 分组后的批次列表，每个批次包含设备信息和元数据。

    Raises:
        BadRequestException: 当设备缺少部门或设备分组时。
    """
    otp_devices: dict[UUID, list[Device]] = {}
    static_devices: list[Device] = []

    for device in devices:
        auth_type = AuthType(device.auth_type)
        if auth_type == AuthType.STATIC:
            static_devices.append(device)
            continue
        if auth_type in (AuthType.OTP_SEED, AuthType.OTP_MANUAL):
            if not device.credential_id:
                raise BadRequestException(message=f"设备 {device.name} 缺少凭据ID")
            otp_devices.setdefault(device.credential_id, []).append(device)
            continue
        static_devices.append(device)

    batches: list[dict[str, Any]] = []

    if static_devices:
        total = len(static_devices)
        total_batches = max(1, (total + chunk_size - 1) // chunk_size)
        for idx in range(0, total, chunk_size):
            batch_devices = static_devices[idx : idx + chunk_size]
            batches.append(
                {
                    "dept_id": None,
                    "device_group": None,
                    "credential_id": None,
                    "devices": batch_devices,
                    "batch_index": idx // chunk_size,
                    "batch_total": total_batches,
                    "group_total": total,
                    "auth_bucket": "static",
                }
            )

    for credential_id, group_devices in otp_devices.items():
        total = len(group_devices)
        total_batches = max(1, (total + chunk_size - 1) // chunk_size)
        device_group = _normalize_device_group(group_devices[0].device_group) if group_devices else None
        dept_id = group_devices[0].dept_id if group_devices else None
        for idx in range(0, total, chunk_size):
            batch_devices = group_devices[idx : idx + chunk_size]
            auth_type = AuthType(batch_devices[0].auth_type) if batch_devices else AuthType.OTP_SEED
            batches.append(
                {
                    "dept_id": dept_id,
                    "device_group": device_group,
                    "credential_id": str(credential_id),
                    "devices": batch_devices,
                    "batch_index": idx // chunk_size,
                    "batch_total": total_batches,
                    "group_total": total,
                    "auth_bucket": auth_type.value,
                }
            )

    return batches
