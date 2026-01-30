"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: presets.py
@DateTime: 2026-01-13 12:45:00
@Docs: 预设模板 API 接口。
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.otp_notice import build_otp_required_response_from_result
from app.core.permissions import PermissionCode
from app.schemas.common import ResponseBase
from app.schemas.preset import PresetDetail, PresetExecuteRequest, PresetExecuteResult, PresetInfo

router = APIRouter(tags=["预设模板"])


@router.get("/", response_model=ResponseBase[list[PresetInfo]], summary="获取预设列表")
async def list_presets(
    preset_service: deps.PresetServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.PRESET_LIST.value])),
) -> Any:
    """获取所有可用的预设模板列表。"""
    presets = await preset_service.list_presets()
    return ResponseBase(data=presets)


@router.get("/{preset_id}", response_model=ResponseBase[PresetDetail], summary="获取预设详情")
async def get_preset(
    preset_id: str,
    preset_service: deps.PresetServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.PRESET_LIST.value])),
) -> Any:
    """获取预设模板详情（含参数 Schema）。"""
    preset = await preset_service.get_preset(preset_id)
    return ResponseBase(data=preset)


@router.post(
    "/{preset_id}/execute",
    response_model=ResponseBase[PresetExecuteResult],
    summary="执行预设操作",
)
async def execute_preset(
    preset_id: str,
    body: PresetExecuteRequest,
    preset_service: deps.PresetServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.PRESET_EXECUTE.value])),
) -> Any:
    """执行预设操作。

    根据预设类型（查看/配置）在目标设备上执行命令，
    返回原始输出和结构化解析结果（如有）。

    Args:
        preset_id (str): 预设 ID。
        body (PresetExecuteRequest): 执行参数（包含设备 ID 和参数）。
        preset_service (PresetService): 预设服务依赖。
        current_user (User): 当前登录用户。
        _: 权限依赖。

    Returns:
        Any: 执行结果或 OTP 验证响应。
    """
    result = await preset_service.execute_preset(
        preset_id=preset_id,
        device_id=body.device_id,
        params=body.params,
    )
    required_response = build_otp_required_response_from_result(
        result.model_dump(),
        message=result.error_message or "需要重新输入 OTP 验证码",
    )
    if required_response:
        return required_response
    return ResponseBase(data=result, message="执行成功" if result.success else "执行失败")
