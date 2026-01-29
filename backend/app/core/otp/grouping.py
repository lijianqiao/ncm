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
