"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: devices.py
@DateTime: 2026-01-09 19:30:00
@Docs: 设备 API 接口 (Devices API).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.enums import DeviceGroup, DeviceStatus, DeviceVendor
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.device import (
    DeviceBatchCreate,
    DeviceBatchDeleteRequest,
    DeviceBatchResult,
    DeviceCreate,
    DeviceLifecycleStatsResponse,
    DeviceListQuery,
    DeviceResponse,
    DeviceStatusBatchTransitionRequest,
    DeviceStatusTransitionRequest,
    DeviceUpdate,
)

router = APIRouter()


@router.get("/", response_model=ResponseBase[PaginatedResponse[DeviceResponse]], summary="获取设备列表")
async def read_devices(
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, max_length=100, description="搜索关键词"),
    vendor: DeviceVendor | None = Query(None, description="厂商筛选"),
    status: DeviceStatus | None = Query(None, description="状态筛选"),
    device_group: DeviceGroup | None = Query(None, description="设备分组筛选"),
    dept_id: UUID | None = Query(None, description="部门筛选"),
) -> ResponseBase[PaginatedResponse[DeviceResponse]]:
    """查询设备列表（分页）。

    支持按关键词、厂商、状态、设备分组、部门筛选。

    Args:
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页数量。
        keyword (str | None): 搜索关键词，匹配名称、IP 或序列号。
        vendor (DeviceVendor | None): 厂商筛选。
        status (DeviceStatus | None): 状态筛选。
        device_group (DeviceGroup | None): 设备分组筛选。
        dept_id (UUID | None): 部门 ID 筛选。

    Returns:
        ResponseBase[PaginatedResponse[DeviceResponse]]: 分页后的设备列表响应。
    """
    query = DeviceListQuery(
        page=page,
        page_size=page_size,
        keyword=keyword,
        vendor=vendor,
        status=status,
        device_group=device_group,
        dept_id=dept_id,
    )
    devices, total = await device_service.get_devices_paginated(query)

    items = [DeviceResponse.model_validate(d) for d in devices]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.get("/recycle-bin", response_model=ResponseBase[PaginatedResponse[DeviceResponse]], summary="获取回收站设备")
async def read_recycle_bin(
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_RECYCLE.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
) -> ResponseBase[PaginatedResponse[DeviceResponse]]:
    """查询回收站中的设备列表（分页）。

    Args:
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页数量。

    Returns:
        ResponseBase[PaginatedResponse[DeviceResponse]]: 分页后的已删除设备列表。
    """
    devices, total = await device_service.get_recycle_bin(page=page, page_size=page_size)

    items = [DeviceResponse.model_validate(d) for d in devices]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.get("/{device_id}", response_model=ResponseBase[DeviceResponse], summary="获取设备详情")
async def read_device(
    device_id: UUID,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_LIST.value])),
) -> Any:
    """根据 ID 获取设备详情。

    Args:
        device_id (UUID): 设备的主键 ID。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceResponse]: 设备详情数据。
    """
    device = await device_service.get_device(device_id)
    return ResponseBase(data=DeviceResponse.model_validate(device))


@router.post("/", response_model=ResponseBase[DeviceResponse], summary="创建设备")
async def create_device(
    obj_in: DeviceCreate,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_CREATE.value])),
) -> Any:
    """添加单一新设备。

    Args:
        obj_in (DeviceCreate): 设备属性数据。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceResponse]: 创建成功后的设备详情。
    """
    device = await device_service.create_device(obj_in)
    return ResponseBase(data=DeviceResponse.model_validate(device), message="设备创建成功")


@router.post("/batch", response_model=ResponseBase[DeviceBatchResult], summary="批量创建设备")
async def batch_create_devices(
    obj_in: DeviceBatchCreate,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_CREATE.value])),
) -> Any:
    """批量创建设备（导入）。

    单次最多支持 500 个设备。逻辑上会跳过重复项或记录错误。

    Args:
        obj_in (DeviceBatchCreate): 包含多个设备属性的列表。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceBatchResult]: 包含成功/失败总数及失败详情的响应。
    """
    result = await device_service.batch_create_devices(obj_in)
    return ResponseBase(
        data=result,
        message=f"批量创建完成：成功 {result.success_count}，失败 {result.failed_count}",
    )


@router.put("/{device_id}", response_model=ResponseBase[DeviceResponse], summary="更新设备")
async def update_device(
    device_id: UUID,
    obj_in: DeviceUpdate,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_UPDATE.value])),
) -> Any:
    """更新指定设备的信息。

    Args:
        device_id (UUID): 设备 ID。
        obj_in (DeviceUpdate): 更新字段。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceResponse]: 更新后的设备详情。
    """
    device = await device_service.update_device(device_id, obj_in)
    return ResponseBase(data=DeviceResponse.model_validate(device), message="设备更新成功")


@router.delete("/{device_id}", response_model=ResponseBase[DeviceResponse], summary="删除设备")
async def delete_device(
    device_id: UUID,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_DELETE.value])),
) -> Any:
    """删除设备（软删除）。

    设备将被移至回收站，不会从数据库物理删除。

    Args:
        device_id (UUID): 设备 ID。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceResponse]: 被删除设备的简要数据。
    """
    device = await device_service.delete_device(device_id)
    return ResponseBase(data=DeviceResponse.model_validate(device), message="设备已移至回收站")


@router.delete("/batch", response_model=ResponseBase[DeviceBatchResult], summary="批量删除设备")
async def batch_delete_devices(
    obj_in: DeviceBatchDeleteRequest,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_DELETE.value])),
) -> Any:
    """批量将选中的设备移入回收站。

    Args:
        obj_in (DeviceBatchDeleteRequest): 包含目标设备 ID 列表。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceBatchResult]: 批量删除操作的结果报告。
    """
    result = await device_service.batch_delete_devices(obj_in.ids)
    return ResponseBase(
        data=result,
        message=f"批量删除完成：成功 {result.success_count}，失败 {result.failed_count}",
    )


@router.post("/batch/restore", response_model=ResponseBase[DeviceBatchResult], summary="批量恢复设备")
async def batch_restore_devices(
    obj_in: DeviceBatchDeleteRequest,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_RESTORE.value])),
) -> Any:
    """批量从回收站中恢复设备。

    Args:
        obj_in (DeviceBatchDeleteRequest): 包含目标设备 ID 列表。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceBatchResult]: 批量恢复操作的结果报告。
    """
    result = await device_service.batch_restore_devices(obj_in.ids)
    return ResponseBase(
        data=result,
        message=f"批量恢复完成：成功 {result.success_count}，失败 {result.failed_count}",
    )


@router.post("/{device_id}/restore", response_model=ResponseBase[DeviceResponse], summary="恢复设备")
async def restore_device(
    device_id: UUID,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_RESTORE.value])),
) -> Any:
    """从回收站中恢复设备到正常状态。

    Args:
        device_id (UUID): 设备 ID。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceResponse]: 恢复后的设备详情。
    """
    device = await device_service.restore_device(device_id)
    return ResponseBase(data=DeviceResponse.model_validate(device), message="设备恢复成功")


@router.post(
    "/{device_id}/status/transition",
    response_model=ResponseBase[DeviceResponse],
    summary="设备状态流转",
)
async def transition_device_status(
    device_id: UUID,
    body: DeviceStatusTransitionRequest,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_STATUS_TRANSITION.value])),
) -> Any:
    """显式执行设备状态变更。

    用于记录设备在资产生命周期中的状态变化（如：入库 -> 在运行 -> 报废）。

    Args:
        device_id (UUID): 设备 ID。
        body (DeviceStatusTransitionRequest): 包含目标状态及变更原因。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前操作人。

    Returns:
        ResponseBase[DeviceResponse]: 状态变更后的设备对象。
    """
    device = await device_service.transition_status(
        device_id,
        to_status=body.to_status,
        reason=body.reason,
        operator_id=current_user.id,
    )
    return ResponseBase(data=DeviceResponse.model_validate(device), message="状态流转成功")


@router.post(
    "/status/transition/batch",
    response_model=ResponseBase[DeviceBatchResult],
    summary="批量设备状态流转",
)
async def batch_transition_device_status(
    body: DeviceStatusBatchTransitionRequest,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_STATUS_TRANSITION.value])),
) -> Any:
    """批量变更一批设备的状态。

    Args:
        body (DeviceStatusBatchTransitionRequest): 包含 ID 列表、目标状态及原因。
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前操作人。

    Returns:
        ResponseBase[DeviceBatchResult]: 批量变更操作的结果报告。
    """
    success_count, failed_items = await device_service.batch_transition_status(
        body.ids,
        to_status=body.to_status,
        reason=body.reason,
        operator_id=current_user.id,
    )
    return ResponseBase(
        data=DeviceBatchResult(
            success_count=success_count,
            failed_count=len(failed_items),
            failed_items=failed_items,
        ),
        message=f"批量状态流转完成：成功 {success_count}，失败 {len(failed_items)}",
    )


@router.get(
    "/lifecycle/stats",
    response_model=ResponseBase[DeviceLifecycleStatsResponse],
    summary="设备生命周期统计",
)
async def lifecycle_stats(
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_STATS_VIEW.value])),
    dept_id: UUID | None = Query(default=None, description="部门筛选"),
    vendor: DeviceVendor | None = Query(default=None, description="厂商筛选"),
) -> Any:
    """根据部门或厂商获取设备资产各状态的数量统计。

    用于仪表盘或其他资产概览界面。

    Args:
        device_service (DeviceService): 设备服务依赖。
        current_user (User): 当前登录用户。
        dept_id (UUID | None): 部门维度过滤。
        vendor (DeviceVendor | None): 厂商维度过滤。

    Returns:
        ResponseBase[DeviceLifecycleStatsResponse]: 包含各状态计数的响应。
    """
    data = await device_service.get_lifecycle_stats(dept_id=dept_id, vendor=vendor.value if vendor else None)
    return ResponseBase(data=DeviceLifecycleStatsResponse(**data))
