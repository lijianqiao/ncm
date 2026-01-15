"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: credentials.py
@DateTime: 2026-01-09 19:35:00
@Docs: 设备分组凭据 API 接口 (Credentials API).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.enums import DeviceGroup
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.credential import (
    CredentialBatchRequest,
    CredentialBatchResult,
    DeviceGroupCredentialCreate,
    DeviceGroupCredentialResponse,
    DeviceGroupCredentialUpdate,
    OTPCacheRequest,
    OTPCacheResponse,
)

router = APIRouter()


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]],
    summary="获取凭据列表",
)
async def read_credentials(
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    dept_id: UUID | None = Query(None, description="部门筛选"),
    device_group: DeviceGroup | None = Query(None, description="设备分组筛选"),
) -> ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]:
    """查询凭据列表（分页）。

    支持按部门和设备分组进行过滤。

    Args:
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页数量。
        dept_id (UUID | None): 部门 ID 筛选。
        device_group (DeviceGroup | None): 设备分组筛选。

    Returns:
        ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]: 分页后的凭据列表响应。
    """
    credentials, total = await credential_service.get_credentials_paginated(
        page=page,
        page_size=page_size,
        dept_id=dept_id,
        device_group=device_group,
    )

    items = [credential_service.to_response(c) for c in credentials]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.get(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="获取凭据详情",
)
async def read_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
) -> Any:
    """根据 ID 获取凭据详情。

    Args:
        credential_id (UUID): 凭据 ID。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceGroupCredentialResponse]: 凭据详情响应。
    """
    credential = await credential_service.get_credential(credential_id)
    return ResponseBase(data=credential_service.to_response(credential))


@router.post(
    "/",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="创建凭据",
)
async def create_credential(
    obj_in: DeviceGroupCredentialCreate,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_CREATE.value])),
) -> Any:
    """创建设备分组凭据。

    每个“部门 + 设备分组”组合只能有一个凭据。OTP 种子将被加密存储。

    Args:
        obj_in (DeviceGroupCredentialCreate): 创建凭据的请求数据。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceGroupCredentialResponse]: 创建成功后的凭据详情。
    """
    credential = await credential_service.create_credential(obj_in)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据创建成功",
    )


@router.put(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="更新凭据",
)
async def update_credential(
    credential_id: UUID,
    obj_in: DeviceGroupCredentialUpdate,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_UPDATE.value])),
) -> Any:
    """更新凭据信息。

    如果提供了新的 OTP 种子，将覆盖原有种子。

    Args:
        credential_id (UUID): 凭据 ID。
        obj_in (DeviceGroupCredentialUpdate): 更新内容。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceGroupCredentialResponse]: 更新后的凭据详情。
    """
    credential = await credential_service.update_credential(credential_id, obj_in)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据更新成功",
    )


@router.delete(
    "/{credential_id:uuid}",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="删除凭据",
)
async def delete_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """删除凭据（软删除）。

    Args:
        credential_id (UUID): 凭据 ID。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceGroupCredentialResponse]: 已删除的凭据简要信息。
    """
    credential = await credential_service.delete_credential(credential_id)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据已删除",
    )


@router.post(
    "/otp/cache",
    response_model=ResponseBase[OTPCacheResponse],
    summary="缓存 OTP 验证码",
)
async def cache_otp(
    request: OTPCacheRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_USE.value])),
) -> Any:
    """缓存用户手动输入的 OTP 验证码。

    该验证码将在 Redis 中短期缓存，供批量设备登录使用。仅对指定了手动输入 OTP 的分组有效。

    Args:
        request (OTPCacheRequest): 包含凭据标识和 OTP 验证码的请求。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[OTPCacheResponse]: 缓存结果详情。
    """
    result = await credential_service.cache_otp(request)
    return ResponseBase(data=result, message=result.message)


@router.delete(
    "/batch",
    response_model=ResponseBase[CredentialBatchResult],
    summary="批量删除凭据",
)
async def batch_delete_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量删除凭据（软删除）。

    Args:
        request (CredentialBatchRequest): 包含凭据ID列表的请求。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[CredentialBatchResult]: 批量删除结果。
    """
    success_count, failed_ids = await credential_service.batch_delete_credentials(request.ids)
    return ResponseBase(
        data=CredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量删除完成，成功 {success_count} 条",
    )


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]],
    summary="获取回收站凭据列表",
)
async def read_recycle_bin_credentials(
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键字搜索"),
) -> ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]:
    """获取回收站凭据列表（已删除的凭据）。

    Args:
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页数量。
        keyword (str | None): 关键字搜索。

    Returns:
        ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]: 分页后的回收站凭据列表。
    """
    credentials, total = await credential_service.get_recycle_bin_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
    )

    items = [credential_service.to_response(c) for c in credentials]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.post(
    "/{credential_id:uuid}/restore",
    response_model=ResponseBase[DeviceGroupCredentialResponse],
    summary="恢复凭据",
)
async def restore_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """恢复已删除的凭据。

    Args:
        credential_id (UUID): 凭据 ID。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeviceGroupCredentialResponse]: 恢复后的凭据详情。
    """
    credential = await credential_service.restore_credential(credential_id)
    return ResponseBase(
        data=credential_service.to_response(credential),
        message="凭据已恢复",
    )


@router.post(
    "/batch/restore",
    response_model=ResponseBase[CredentialBatchResult],
    summary="批量恢复凭据",
)
async def batch_restore_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量恢复已删除的凭据。

    Args:
        request (CredentialBatchRequest): 包含凭据ID列表的请求。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[CredentialBatchResult]: 批量恢复结果。
    """
    success_count, failed_ids = await credential_service.batch_restore_credentials(request.ids)
    return ResponseBase(
        data=CredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量恢复完成，成功 {success_count} 条",
    )


@router.delete(
    "/{credential_id:uuid}/hard",
    response_model=ResponseBase[dict],
    summary="彻底删除凭据",
)
async def hard_delete_credential(
    credential_id: UUID,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """彻底删除凭据（硬删除，不可恢复）。

    Args:
        credential_id (UUID): 凭据 ID。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[dict]: 删除结果。
    """
    await credential_service.hard_delete_credential(credential_id)
    return ResponseBase(
        data={"message": "凭据已彻底删除"},
        message="凭据已彻底删除",
    )


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[CredentialBatchResult],
    summary="批量彻底删除凭据",
)
async def batch_hard_delete_credentials(
    request: CredentialBatchRequest,
    credential_service: deps.CredentialServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.CREDENTIAL_DELETE.value])),
) -> Any:
    """批量彻底删除凭据（硬删除，不可恢复）。

    Args:
        request (CredentialBatchRequest): 包含凭据ID列表的请求。
        credential_service (CredentialService): 凭据服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[CredentialBatchResult]: 批量彻底删除结果。
    """
    success_count, failed_ids = await credential_service.batch_hard_delete_credentials(request.ids)
    return ResponseBase(
        data=CredentialBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量彻底删除完成，成功 {success_count} 条",
    )
