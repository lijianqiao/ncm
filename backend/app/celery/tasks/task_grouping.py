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
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    text = str(value)
    if text.startswith("DeviceGroup."):
        text = text.split(".", maxsplit=1)[-1]
    return text


def build_backup_batches(devices: list[Device], *, chunk_size: int = 100) -> list[dict[str, Any]]:
    """
    批量备份分组规则：
    - 非 otp_manual：合并为一个任务，按 100 台分批
    - otp_manual：按 (dept_id, device_group) 分组后再按 100 台分批
    """
    otp_manual_devices: dict[tuple[UUID, str], list[Device]] = {}
    non_otp_devices: list[Device] = []

    for device in devices:
        auth_type = AuthType(device.auth_type)
        if auth_type == AuthType.OTP_MANUAL:
            if not device.dept_id or not device.device_group:
                raise BadRequestException(message=f"设备 {device.name} 缺少部门或设备分组")
            group_value = _normalize_device_group(device.device_group) or str(device.device_group)
            key = (device.dept_id, group_value)
            otp_manual_devices.setdefault(key, []).append(device)
        else:
            non_otp_devices.append(device)

    batches: list[dict[str, Any]] = []

    if non_otp_devices:
        total = len(non_otp_devices)
        total_batches = max(1, (total + chunk_size - 1) // chunk_size)
        for idx in range(0, total, chunk_size):
            batch_devices = non_otp_devices[idx : idx + chunk_size]
            batches.append(
                {
                    "dept_id": None,
                    "device_group": None,
                    "devices": batch_devices,
                    "batch_index": idx // chunk_size,
                    "batch_total": total_batches,
                    "group_total": total,
                    "auth_bucket": "non_otp",
                }
            )

    for (dept_id, device_group), group_devices in otp_manual_devices.items():
        total = len(group_devices)
        total_batches = max(1, (total + chunk_size - 1) // chunk_size)
        for idx in range(0, total, chunk_size):
            batch_devices = group_devices[idx : idx + chunk_size]
            batches.append(
                {
                    "dept_id": dept_id,
                    "device_group": device_group,
                    "devices": batch_devices,
                    "batch_index": idx // chunk_size,
                    "batch_total": total_batches,
                    "group_total": total,
                    "auth_bucket": "otp_manual",
                }
            )

    return batches
