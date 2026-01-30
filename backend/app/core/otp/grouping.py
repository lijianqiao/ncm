"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: grouping.py
@DateTime: 2026-01-30 12:02:00
@Docs: OTP 设备分组模块 (OTP Device Grouping).

提供设备按部门 ID 和设备分组进行分组和分批的功能。
"""

from math import ceil
from typing import Any
from uuid import UUID


def split_devices_by_group(
    devices: list[Any],
    *,
    chunk_size: int = 100,
) -> list[dict[str, Any]]:
    """
    按 (dept_id, device_group) 分组，并按 chunk_size 分批。

    将设备列表按部门 ID 和设备分组进行分组，然后对每个分组按指定大小进行分批。

    Args:
        devices: 设备对象列表
        chunk_size: 每批大小（默认 100）

    Returns:
        list[dict[str, Any]]: 分批结果列表，每项包含：
            - dept_id: 部门 ID
            - device_group: 设备分组
            - devices: 该批次的设备列表
            - batch_index: 批次索引（从 0 开始）
            - batch_total: 该分组的总批次数
            - group_total: 该分组的总设备数
    """
    grouped: dict[tuple[UUID | None, str | None], list[Any]] = {}
    for device in devices:
        key = (getattr(device, "dept_id", None), getattr(device, "device_group", None))
        grouped.setdefault(key, []).append(device)

    batches: list[dict[str, Any]] = []
    for (dept_id, device_group), group_devices in grouped.items():
        total = len(group_devices)
        total_batches = max(1, ceil(total / chunk_size))
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
                }
            )
    return batches
