"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: menus.py
@DateTime: 2025-12-30 14:25:00
@Docs: 菜单 API 接口 (Menus API).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.enums import MenuType
from app.core.permissions import PermissionCode
from app.schemas.common import (
    BatchDeleteRequest,
    BatchOperationResult,
    BatchRestoreRequest,
    PaginatedResponse,
    ResponseBase,
)
from app.schemas.menu import MenuCreate, MenuResponse, MenuUpdate

router = APIRouter()


@router.get("/options", response_model=ResponseBase[list[MenuResponse]], summary="获取可分配菜单选项")
async def get_menu_options(
    current_user: deps.CurrentUser,
    menu_service: deps.MenuServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_OPTIONS_LIST.value])),
) -> ResponseBase[list[MenuResponse]]:
    """获取可分配菜单选项（树结构）。

    用于角色创建/编辑时选择可分配菜单（包含隐藏权限点）。

    Args:
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。
        _ (User): 权限依赖（需要 menu:options:list）。

    Returns:
        ResponseBase[list[MenuResponse]]: 菜单选项树。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足时。
    """

    menus = await menu_service.get_menu_options_tree()
    return ResponseBase(data=menus)


@router.get("/me", response_model=ResponseBase[list[MenuResponse]], summary="获取我的菜单")
async def get_my_menus(
    current_user: deps.CurrentUser,
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[list[MenuResponse]]:
    """获取当前登录用户可见的导航菜单树。

    不包含隐藏权限点（is_hidden=true 的菜单节点不会返回），但隐藏权限点会影响父级菜单的可见性判定。

    Args:
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[list[MenuResponse]]: 当前用户可见的导航菜单树。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
    """

    menus = await menu_service.get_my_menus_tree(current_user)
    return ResponseBase(data=menus)


@router.get("/", response_model=ResponseBase[PaginatedResponse[MenuResponse]], summary="获取菜单列表")
async def read_menus(
    current_user: deps.CurrentUser,
    menu_service: deps.MenuServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
    is_hidden: bool | None = None,
    type: MenuType | None = None,
) -> ResponseBase[PaginatedResponse[MenuResponse]]:
    """
    获取菜单列表 (分页)。

    查询系统菜单记录，支持分页。按排序字段排序。

    Args:
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.
        is_hidden (bool | None, optional): 是否隐藏过滤. Defaults to None.
        type (MenuType | None, optional): 菜单类型过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[MenuResponse]]: 分页后的菜单列表。
    """
    menus, total = await menu_service.get_menus_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_active=is_active,
        is_hidden=is_hidden,
        type=type,
    )
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=menus))


@router.post("/", response_model=ResponseBase[MenuResponse], summary="创建菜单")
async def create_menu(
    *,
    menu_in: MenuCreate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_CREATE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[MenuResponse]:
    """
    创建新菜单。

    创建新的系统菜单或权限节点。

    Args:
        menu_in (MenuCreate): 菜单创建数据 (标题, 路径, 类型等)。
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[MenuResponse]: 创建成功的菜单对象。
    """
    menu = await menu_service.create_menu(obj_in=menu_in)
    return ResponseBase(data=menu)


@router.delete("/batch", response_model=ResponseBase[BatchOperationResult], summary="批量删除菜单")
async def batch_delete_menus(
    *,
    request: BatchDeleteRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_DELETE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """
    批量删除菜单。

    支持软删除和硬删除。如果存在子菜单，将级联删除或校验（取决于具体实现策略）。

    Args:
        request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。
    """
    result = await menu_service.batch_delete_menus(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(data=result)


@router.put("/{id}", response_model=ResponseBase[MenuResponse], summary="更新菜单")
async def update_menu(
    *,
    id: UUID,
    menu_in: MenuUpdate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_UPDATE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[MenuResponse]:
    """
    更新菜单。

    更新指定 ID 的菜单信息。

    Args:
        id (UUID): 菜单 ID。
        menu_in (MenuUpdate): 菜单更新数据。
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[MenuResponse]: 更新后的菜单对象。
    """
    menu = await menu_service.update_menu(id=id, obj_in=menu_in)
    return ResponseBase(data=menu)


@router.get("/recycle-bin", response_model=ResponseBase[PaginatedResponse[MenuResponse]], summary="获取菜单回收站列表")
async def get_recycle_bin(
    *,
    page: int = 1,
    page_size: int = 20,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_RECYCLE.value])),
    menu_service: deps.MenuServiceDep,
    keyword: str | None = None,
    is_active: bool | None = None,
    is_hidden: bool | None = None,
    type: MenuType | None = None,
) -> ResponseBase[PaginatedResponse[MenuResponse]]:
    """
    获取已删除的菜单列表 (回收站)。
    仅限超级管理员。

    Args:
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 menu:recycle）。
        menu_service (MenuService): 菜单服务依赖。
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.
        is_hidden (bool | None, optional): 是否隐藏过滤. Defaults to None.
        type (MenuType | None, optional): 菜单类型过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[MenuResponse]]: 分页后的回收站菜单列表。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足或非超级管理员时。
    """
    menus, total = await menu_service.get_deleted_menus(
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_active=is_active,
        is_hidden=is_hidden,
        type=type,
    )
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=menus))


@router.delete("/{id}", response_model=ResponseBase[MenuResponse], summary="删除菜单")
async def delete_menu(
    *,
    id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_DELETE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[MenuResponse]:
    """
    删除菜单。

    删除指定 ID 的菜单。

    Args:
        id (UUID): 菜单 ID。
        current_user (User): 当前登录用户。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[MenuResponse]: 已删除的菜单对象信息。
    """
    menu = await menu_service.delete_menu(id=id)
    return ResponseBase(data=menu)


@router.post("/batch/restore", response_model=ResponseBase[BatchOperationResult], summary="批量恢复菜单")
async def batch_restore_menus(
    *,
    request: BatchRestoreRequest,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_RESTORE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """批量恢复菜单。

    从回收站中批量恢复软删除菜单。
    需要超级管理员权限。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 menu:restore）。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """

    result = await menu_service.batch_restore_menus(ids=request.ids)
    return ResponseBase(data=result)


@router.post("/{id}/restore", response_model=ResponseBase[MenuResponse], summary="恢复已删除菜单")
async def restore_menu(
    *,
    id: UUID,
    active_superuser: deps.User = Depends(deps.get_current_active_superuser),
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_RESTORE.value])),
    menu_service: deps.MenuServiceDep,
) -> ResponseBase[MenuResponse]:
    """
    恢复已删除菜单。

    从回收站中恢复指定菜单。
    需要超级管理员权限。

    Args:
        id (UUID): 菜单 ID。
        active_superuser (User): 超级管理员权限验证。
        _ (User): 权限依赖（需要 menu:restore）。
        menu_service (MenuService): 菜单服务依赖。

    Returns:
        ResponseBase[MenuResponse]: 恢复后的菜单对象。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足或非超级管理员时。
        NotFoundException: 菜单不存在时。
    """
    menu = await menu_service.restore_menu(id=id)
    return ResponseBase(data=menu, message="菜单恢复成功")
