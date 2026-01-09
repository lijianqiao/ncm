"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: depts.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门 API 接口 (Departments API)。
"""

from uuid import UUID

from fastapi import APIRouter, Depends

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
    current_user: deps.CurrentUser,
    dept_service: deps.DeptServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_LIST.value])),
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ResponseBase[list[DeptResponse]]:
    """
    获取部门树结构。

    Args:
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。
        keyword (str | None, optional): 关键词过滤(部门名称/编码/负责人). Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[list[DeptResponse]]: 部门树。
    """
    tree = await dept_service.get_dept_tree(keyword=keyword, is_active=is_active)
    return ResponseBase(data=tree)


@router.get("/", response_model=ResponseBase[PaginatedResponse[DeptResponse]], summary="获取部门列表")
async def read_depts(
    current_user: deps.CurrentUser,
    dept_service: deps.DeptServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[DeptResponse]]:
    """
    获取部门列表（分页）。

    Args:
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

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


@router.post("/", response_model=ResponseBase[DeptResponse], summary="创建部门")
async def create_dept(
    *,
    dept_in: DeptCreate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_CREATE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[DeptResponse]:
    """
    创建新部门。

    Args:
        dept_in (DeptCreate): 部门创建数据。
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。

    Returns:
        ResponseBase[DeptResponse]: 创建成功的部门对象。
    """
    dept = await dept_service.create_dept(obj_in=dept_in)
    return ResponseBase(data=dept)


@router.put("/{id}", response_model=ResponseBase[DeptResponse], summary="更新部门")
async def update_dept(
    *,
    id: UUID,
    dept_in: DeptUpdate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_UPDATE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[DeptResponse]:
    """
    更新部门。

    Args:
        id (UUID): 部门 ID。
        dept_in (DeptUpdate): 部门更新数据。
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。

    Returns:
        ResponseBase[DeptResponse]: 更新后的部门对象。
    """
    dept = await dept_service.update_dept(dept_id=id, obj_in=dept_in)
    return ResponseBase(data=dept, message="部门更新成功")


@router.delete("/batch", response_model=ResponseBase[BatchOperationResult], summary="批量删除部门")
async def batch_delete_depts(
    *,
    request: BatchDeleteRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """
    批量删除部门。

    Args:
        request (BatchDeleteRequest): 批量删除请求体。
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果。
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
    *,
    id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_DELETE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[DeptResponse]:
    """
    删除部门（软删除）。

    Args:
        id (UUID): 部门 ID。
        current_user (User): 当前登录用户。
        dept_service (DeptService): 部门服务依赖。

    Returns:
        ResponseBase[DeptResponse]: 删除后的部门对象。
    """
    dept = await dept_service.delete_dept(dept_id=id)
    return ResponseBase(data=dept, message="部门删除成功")


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeptResponse]],
    summary="获取部门回收站列表",
)
async def get_recycle_bin(
    *,
    page: int = 1,
    page_size: int = 20,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RECYCLE.value])),
    dept_service: deps.DeptServiceDep,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[DeptResponse]]:
    """
    获取已删除的部门列表（回收站）。
    仅限超级管理员。

    Args:
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        active_superuser (User): 超级管理员权限验证。
        dept_service (DeptService): 部门服务依赖。
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[DeptResponse]]: 分页后的回收站部门列表。
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


@router.post("/batch/restore", response_model=ResponseBase[BatchOperationResult], summary="批量恢复部门")
async def batch_restore_depts(
    *,
    request: BatchRestoreRequest,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RESTORE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """
    批量恢复部门。
    需要超级管理员权限。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体。
        active_superuser (User): 超级管理员权限验证。
        dept_service (DeptService): 部门服务依赖。

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
    *,
    id: UUID,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEPT_RESTORE.value])),
    dept_service: deps.DeptServiceDep,
) -> ResponseBase[DeptResponse]:
    """
    恢复已删除部门。
    需要超级管理员权限。

    Args:
        id (UUID): 部门 ID。
        active_superuser (User): 超级管理员权限验证。
        dept_service (DeptService): 部门服务依赖。

    Returns:
        ResponseBase[DeptResponse]: 恢复后的部门对象。
    """
    dept = await dept_service.restore_dept(dept_id=id)
    return ResponseBase(data=dept, message="部门恢复成功")
