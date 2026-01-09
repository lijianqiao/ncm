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
    DeviceListQuery,
    DeviceResponse,
    DeviceUpdate,
)

router = APIRouter()


@router.get("/", response_model=ResponseBase[PaginatedResponse[DeviceResponse]], summary="获取设备列表")
async def read_devices(
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, max_length=100, description="搜索关键词"),
    vendor: DeviceVendor | None = Query(None, description="厂商筛选"),
    status: DeviceStatus | None = Query(None, description="状态筛选"),
    device_group: DeviceGroup | None = Query(None, description="设备分组筛选"),
    dept_id: UUID | None = Query(None, description="部门筛选"),
) -> Any:
    """
    查询设备列表 (分页)。

    支持按关键词、厂商、状态、设备分组、部门筛选。
    需要设备-列表权限。
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
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> Any:
    """
    查询回收站中的设备列表 (分页)。

    需要设备-回收站权限。
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
    """
    根据 ID 获取设备详情。

    需要设备-列表权限。
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
    """
    创建新设备。

    需要设备-创建权限。
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
    """
    批量创建设备。

    最多支持 500 个设备同时导入。
    需要设备-创建权限。
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
    """
    更新设备信息。

    需要设备-更新权限。
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
    """
    删除设备（软删除）。

    设备将被移至回收站，可通过恢复接口恢复。
    需要设备-删除权限。
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
    """
    批量删除设备（软删除）。

    需要设备-删除权限。
    """
    result = await device_service.batch_delete_devices(obj_in.ids)
    return ResponseBase(
        data=result,
        message=f"批量删除完成：成功 {result.success_count}，失败 {result.failed_count}",
    )


@router.post("/{device_id}/restore", response_model=ResponseBase[DeviceResponse], summary="恢复设备")
async def restore_device(
    device_id: UUID,
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_RESTORE.value])),
) -> Any:
    """
    从回收站恢复设备。

    需要设备-恢复权限。
    """
    device = await device_service.restore_device(device_id)
    return ResponseBase(data=DeviceResponse.model_validate(device), message="设备恢复成功")
