"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: depts.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 API 接口 (Departments API)。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.permissions import PermissionCode
from app.schemas.common import (
    BatchDeleteRequest,
    BatchOperationResult,
    BatchRestoreRequest,
    PaginatedResponse,
    ResponseBase,
)
from app.schemas.dept import DeptCreate, DeptResponse, DeptUpdate

router = APIRouter()


@router.get("/tree", response_model=ResponseBase[list[DeptResponse]], summary="获取部门树")
async def get_dept_tree(
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_LIST.value])),
    keyword: str | None = Query(default=None, description="关键词过滤"),
    is_active: bool | None = Query(default=None, description="是否启用过滤"),
) -> ResponseBase[list[DeptResponse]]:
    """获取部门树结构。

    Args:
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。
        keyword (str | None): 关键词过滤 (名称或标识)。
        is_active (bool | None): 是否启用过滤。

    Returns:
        ResponseBase[list[DeptResponse]]: 部门树形结构列表。
    """
    tree = await dept_service.get_dept_tree(keyword=keyword, is_active=is_active)
    return ResponseBase(data=tree)


@router.get("/", response_model=ResponseBase[PaginatedResponse[DeptResponse]], summary="获取部门列表")
async def read_depts(
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_LIST.value])),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(default=None, description="关键词过滤"),
    is_active: bool | None = Query(default=None, description="是否启用过滤"),
) -> ResponseBase[PaginatedResponse[DeptResponse]]:
    """获取部门列表（分页）。

    Args:
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页数量。
        keyword (str | None): 关键词过滤。
        is_active (bool | None): 是否启用过滤。

    Returns:
        ResponseBase[PaginatedResponse[DeptResponse]]: 分页后的部门列表。
    """
    depts, total = await dept_service.get_depts_paginated(
        page=page, page_size=page_size, keyword=keyword, is_active=is_active
    )
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=depts,
        )
    )


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeptResponse]],
    summary="获取部门回收站列表",
)
async def get_recycle_bin(
    dept_service: deps.DeptServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RECYCLE.value])),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(default=None, description="关键词过滤"),
    is_active: bool | None = Query(default=None, description="是否启用过滤"),
) -> ResponseBase[PaginatedResponse[DeptResponse]]:
    """获取已删除的部门列表（回收站）。

    仅限超级管理员访问。

    Args:
        dept_service (DeptService): 部门服务依赖。
        active_superuser (User): 超级管理员权限验证。
        page (int): 页码。
        page_size (int): 每页数量。
        keyword (str | None): 关键词过滤。
        is_active (bool | None): 是否启用过滤。

    Returns:
        ResponseBase[PaginatedResponse[DeptResponse]]: 回收站中的部门列表。
    """
    depts, total = await dept_service.get_deleted_depts(
        page=page, page_size=page_size, keyword=keyword, is_active=is_active
    )
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=depts,
        )
    )


@router.get("/{id}", response_model=ResponseBase[DeptResponse], summary="获取部门详情")
async def get_dept(
    id: UUID,
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_LIST.value])),
) -> ResponseBase[DeptResponse]:
    """根据 ID 获取部门详情。

    Args:
        id (UUID): 部门 ID。
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeptResponse]: 部门详细信息。
    """
    dept = await dept_service.get_dept(dept_id=id)
    return ResponseBase(data=dept)


@router.post("/", response_model=ResponseBase[DeptResponse], summary="创建部门")
async def create_dept(
    dept_in: DeptCreate,
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_CREATE.value])),
) -> ResponseBase[DeptResponse]:
    """创建新部门。

    Args:
        dept_in (DeptCreate): 部门创建数据。
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeptResponse]: 创建成功的部门信息。
    """
    dept = await dept_service.create_dept(obj_in=dept_in)
    return ResponseBase(data=dept, message="部门创建成功")


@router.put("/{id}", response_model=ResponseBase[DeptResponse], summary="更新部门")
async def update_dept(
    id: UUID,
    dept_in: DeptUpdate,
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_UPDATE.value])),
) -> ResponseBase[DeptResponse]:
    """更新部门信息。

    Args:
        id (UUID): 部门 ID。
        dept_in (DeptUpdate): 部门更新数据。
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeptResponse]: 更新后的部门信息。
    """
    dept = await dept_service.update_dept(dept_id=id, obj_in=dept_in)
    return ResponseBase(data=dept, message="部门更新成功")


@router.delete("/batch", response_model=ResponseBase[BatchOperationResult], summary="批量删除部门")
async def batch_delete_depts(
    request: BatchDeleteRequest,
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量删除部门。

    Args:
        request (BatchDeleteRequest): 批量删除请求体。
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[BatchOperationResult]: 批量删除结果。
    """
    success_count, failed_ids = await dept_service.batch_delete_depts(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功删除 {success_count} 个部门" if not failed_ids else "部分删除成功",
        )
    )


@router.delete("/{id}", response_model=ResponseBase[DeptResponse], summary="删除部门")
async def delete_dept(
    id: UUID,
    dept_service: deps.DeptServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
) -> ResponseBase[DeptResponse]:
    """删除部门（软删除）。

    Args:
        id (UUID): 部门 ID。
        dept_service (DeptService): 部门服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DeptResponse]: 被删除的部门信息。
    """
    dept = await dept_service.delete_dept(dept_id=id)
    return ResponseBase(data=dept, message="部门删除成功")


@router.post("/batch/restore", response_model=ResponseBase[BatchOperationResult], summary="批量恢复部门")
async def batch_restore_depts(
    request: BatchRestoreRequest,
    dept_service: deps.DeptServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RESTORE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量恢复部门。

    仅限超级管理员访问。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体。
        dept_service (DeptService): 部门服务依赖。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """
    success_count, failed_ids = await dept_service.batch_restore_depts(ids=request.ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功恢复 {success_count} 个部门" if not failed_ids else "部分恢复成功",
        )
    )


@router.post("/{id}/restore", response_model=ResponseBase[DeptResponse], summary="恢复已删除部门")
async def restore_dept(
    id: UUID,
    dept_service: deps.DeptServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RESTORE.value])),
) -> ResponseBase[DeptResponse]:
    """恢复已删除部门。

    仅限超级管理员访问。

    Args:
        id (UUID): 部门 ID。
        dept_service (DeptService): 部门服务依赖。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[DeptResponse]: 恢复后的部门信息。
    """
    dept = await dept_service.restore_dept(dept_id=id)
    return ResponseBase(data=dept, message="部门恢复成功")


@router.delete("/{id}/hard", response_model=ResponseBase[dict], summary="彻底删除部门")
async def hard_delete_dept(
    id: UUID,
    dept_service: deps.DeptServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
) -> ResponseBase[dict]:
    """彻底删除部门（硬删除，不可恢复）。

    仅限超级管理员访问。

    Args:
        id (UUID): 部门 ID。
        dept_service (DeptService): 部门服务依赖。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[dict]: 删除结果。
    """
    await dept_service.hard_delete_dept(dept_id=id)
    return ResponseBase(
        data={"message": "部门已彻底删除"},
        message="部门已彻底删除",
    )


@router.delete("/batch/hard", response_model=ResponseBase[BatchOperationResult], summary="批量彻底删除部门")
async def batch_hard_delete_depts(
    request: BatchDeleteRequest,
    dept_service: deps.DeptServiceDep,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量彻底删除部门（硬删除，不可恢复）。

    仅限超级管理员访问。

    Args:
        request (BatchDeleteRequest): 批量删除请求体。
        dept_service (DeptService): 部门服务依赖。
        active_superuser (User): 超级管理员权限验证。

    Returns:
        ResponseBase[BatchOperationResult]: 批量删除结果。
    """
    success_count, failed_ids = await dept_service.batch_hard_delete_depts(ids=request.ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功彻底删除 {success_count} 个部门" if not failed_ids else "部分彻底删除成功",
        )
    )
