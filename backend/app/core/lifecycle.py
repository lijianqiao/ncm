"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: lifecycle.py
@DateTime: 2026-01-09 21:05:00
@Docs: 资产生命周期状态机规则（设备状态流转约束）。
"""

from app.core.enums import DeviceStatus
from app.core.exceptions import BadRequestException

# 允许的生命周期状态流转矩阵（最小可用版本）
#
# 说明：
# - 复用现有 Device.status（DeviceStatus）作为生命周期状态。
# - active 代表“可自动任务执行”的 operational 状态，允许 in_use <-> active 切换。
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    DeviceStatus.IN_STOCK.value: {DeviceStatus.IN_USE.value},
    DeviceStatus.IN_USE.value: {
        DeviceStatus.MAINTENANCE.value,
        DeviceStatus.RETIRED.value,
        DeviceStatus.ACTIVE.value,
    },
    DeviceStatus.ACTIVE.value: {
        DeviceStatus.IN_USE.value,
        DeviceStatus.MAINTENANCE.value,
        DeviceStatus.RETIRED.value,
    },
    DeviceStatus.MAINTENANCE.value: {DeviceStatus.IN_USE.value, DeviceStatus.RETIRED.value},
    DeviceStatus.RETIRED.value: set(),
}


def validate_transition(from_status: str, to_status: str) -> None:
    """校验状态流转是否允许。"""
    if from_status == to_status:
        return

    allowed = ALLOWED_TRANSITIONS.get(from_status)
    if allowed is None:
        raise BadRequestException(message=f"未知的设备状态: {from_status}")

    if to_status not in allowed:
        raise BadRequestException(message=f"不允许的状态流转: {from_status} -> {to_status}")
