"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: roles.py
@DateTime: 2025-12-30 14:20:00
@Docs: 角色 API 接口 (Roles API).
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
from app.schemas.role import RoleCreate, RoleMenusUpdateRequest, RoleResponse, RoleUpdate

router = APIRouter()


@router.get("/", response_model=ResponseBase[PaginatedResponse[RoleResponse]], summary="获取角色列表")
async def read_roles(
    role_service: deps.RoleServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[RoleResponse]]:
    """
    获取角色列表 (分页)。

    查询系统角色记录，支持分页。

    Args:
        role_service (RoleService): 角色服务依赖。
        current_user (User): 当前登录用户。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[RoleResponse]]: 分页后的角色列表。
    """
    roles, total = await role_service.get_roles_paginated(
        page=page, page_size=page_size, keyword=keyword, is_active=is_active
    )
    return ResponseBase(
        data=PaginatedResponse(
            total=total, page=page, page_size=page_size, items=[RoleResponse.model_validate(r) for r in roles]
        )
    )


@router.post("/", response_model=ResponseBase[RoleResponse], summary="创建角色")
async def create_role(
    *,
    role_in: RoleCreate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_CREATE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[RoleResponse]:
    """
    创建新角色。

    创建新的系统角色。

    Args:
        role_in (RoleCreate): 角色创建数据 (名称, 标识, 描述等)。
        current_user (User): 当前登录用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[RoleResponse]: 创建成功的角色对象。
    """
    role = await role_service.create_role(obj_in=role_in)
    return ResponseBase(data=RoleResponse.model_validate(role))


@router.delete("/batch", response_model=ResponseBase[BatchOperationResult], summary="批量删除角色")
async def batch_delete_roles(
    *,
    request: BatchDeleteRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_DELETE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """
    批量删除角色。

    支持软删除和硬删除。

    Args:
        request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
        current_user (User): 当前登录用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。
    """
    success_count, failed_ids = await role_service.batch_delete_roles(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功删除 {success_count} 个角色" if not failed_ids else "部分删除成功",
        )
    )


@router.put("/{id}", response_model=ResponseBase[RoleResponse], summary="更新角色")
async def update_role(
    *,
    id: UUID,
    role_in: RoleUpdate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_UPDATE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[RoleResponse]:
    """
    更新角色。

    更新指定 ID 的角色信息。

    Args:
        id (UUID): 角色 ID。
        role_in (RoleUpdate): 角色更新数据。
        current_user (User): 当前登录用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[RoleResponse]: 更新后的角色对象。
    """
    role = await role_service.update_role(id=id, obj_in=role_in)
    return ResponseBase(data=RoleResponse.model_validate(role))


@router.get("/recycle-bin", response_model=ResponseBase[PaginatedResponse[RoleResponse]], summary="获取角色回收站列表")
async def get_recycle_bin(
    *,
    page: int = 1,
    page_size: int = 20,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_RECYCLE.value])),
    role_service: deps.RoleServiceDep,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[RoleResponse]]:
    """
    获取已删除的角色列表 (回收站)。
    仅限超级管理员。

    Args:
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 role:recycle）。
        role_service (RoleService): 角色服务依赖。
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[RoleResponse]]: 分页后的回收站角色列表。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足或非超级管理员时。
    """
    roles, total = await role_service.get_deleted_roles(
        page=page, page_size=page_size, keyword=keyword, is_active=is_active
    )
    return ResponseBase(
        data=PaginatedResponse(
            total=total, page=page, page_size=page_size, items=[RoleResponse.model_validate(r) for r in roles]
        )
    )


@router.delete("/{id}", response_model=ResponseBase[RoleResponse], summary="删除角色")
async def delete_role(
    *,
    id: UUID,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_DELETE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[RoleResponse]:
    """
    删除角色 (软删除)。

    Args:
        id (UUID): 角色 ID。
        active_superuser (User): 当前登录超级用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[RoleResponse]: 删除后的角色对象。
    """
    role = await role_service.delete_role(id=id)
    return ResponseBase(data=RoleResponse.model_validate(role))


@router.post("/batch/restore", response_model=ResponseBase[BatchOperationResult], summary="批量恢复角色")
async def batch_restore_roles(
    *,
    request: BatchRestoreRequest,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_RESTORE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """批量恢复角色。

    从回收站中批量恢复软删除角色。
    需要超级管理员权限。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 role:restore）。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """

    success_count, failed_ids = await role_service.batch_restore_roles(ids=request.ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功恢复 {success_count} 个角色" if not failed_ids else "部分恢复成功",
        )
    )


@router.post("/{id}/restore", response_model=ResponseBase[RoleResponse], summary="恢复已删除角色")
async def restore_role(
    *,
    id: UUID,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_RESTORE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[RoleResponse]:
    """
    恢复已删除角色。

    从回收站中恢复指定角色。
    需要超级管理员权限。

    Args:
        id (UUID): 角色 ID。
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 role:restore）。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[RoleResponse]: 恢复后的角色对象。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足或非超级管理员时。
        NotFoundException: 角色不存在时。
    """
    role = await role_service.restore_role(id=id)
    return ResponseBase(data=RoleResponse.model_validate(role), message="角色恢复成功")


@router.get("/{id}/menus", response_model=ResponseBase[list[UUID]], summary="获取角色菜单")
async def get_role_menus(
    *,
    id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_MENUS_LIST.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[list[UUID]]:
    """获取指定角色当前已绑定的所有菜单和权限点 ID。

    用于角色编辑界面回显已勾选的权限树。

    Args:
        id (UUID): 角色 ID。
        current_user (User): 当前登录用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[list[UUID]]: 菜单 ID 列表。
    """

    menu_ids = await role_service.get_role_menu_ids(role_id=id)
    return ResponseBase(data=menu_ids)


@router.put("/{id}/menus", response_model=ResponseBase[list[UUID]], summary="设置角色菜单")
async def set_role_menus(
    *,
    id: UUID,
    req: RoleMenusUpdateRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ROLE_MENUS_UPDATE.value])),
    role_service: deps.RoleServiceDep,
) -> ResponseBase[list[UUID]]:
    """全量更新角色的菜单和权限绑定关系。

    Args:
        id (UUID): 角色 ID。
        req (RoleMenusUpdateRequest): 包含新的菜单 ID 集合。
        current_user (User): 当前登录用户。
        role_service (RoleService): 角色服务依赖。

    Returns:
        ResponseBase[list[UUID]]: 更新后的菜单 ID 列表。
    """

    menu_ids = await role_service.set_role_menus(role_id=id, menu_ids=req.menu_ids)
    return ResponseBase(data=menu_ids, message="角色菜单设置成功")
