"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: users.py
@DateTime: 2025-12-30 11:55:00
@Docs: 用户 API 接口 (Users API).
"""

from typing import Any
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
from app.schemas.role import RoleResponse
from app.schemas.user import (
    ChangePasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserMeUpdate,
    UserResponse,
    UserRolesUpdateRequest,
    UserUpdate,
)

router = APIRouter()


# ===== 列表查询 =====


@router.get("/", response_model=ResponseBase[PaginatedResponse[UserResponse]], summary="获取用户列表")
async def read_users(
    user_service: deps.UserServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_superuser: bool | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[UserResponse]]:
    """
    查询用户列表 (分页)。

    获取所有系统用户，支持分页。需要用户-列表权限。

    Args:
        user_service (UserService): 用户服务依赖。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:list）。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_superuser (bool | None, optional): 是否超级管理员过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[UserResponse]]: 分页后的用户列表。
    """
    users, total = await user_service.get_users_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_superuser=is_superuser,
        is_active=is_active,
    )

    items = [
        UserResponse.model_validate(u).model_copy(update={"dept_name": u.dept.name if u.dept else None}) for u in users
    ]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


# ===== 详情 =====


@router.get("/{user_id:uuid}", response_model=ResponseBase[UserResponse], summary="获取特定用户信息")
async def read_user_by_id(
    *,
    user_id: UUID,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_LIST.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[UserResponse]:
    """
    获取特定用户的详细信息 (管理员)。

    Args:
        user_id (UUID): 目标用户 ID。
        _ (User): 权限依赖（需要 user:list）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[UserResponse]: 用户详细信息。
    """
    user = await user_service.get_user(user_id=user_id)
    return ResponseBase(data=UserResponse.model_validate(user))


# ===== 创建 =====


@router.post("/", response_model=ResponseBase[UserResponse], summary="创建用户")
async def create_user(
    *,
    user_in: UserCreate,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_CREATE.value])),
    user_service: deps.UserServiceDep,
) -> Any:
    """
    创建新用户。

    注册新的系统用户。需要用户-创建权限。

    Args:
        user_in (UserCreate): 用户创建数据 (用户名, 密码, 邮箱等)。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:create）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[UserResponse]: 创建成功的用户对象。
    """
    user = await user_service.create_user(obj_in=user_in)
    return ResponseBase(data=UserResponse.model_validate(user))


# ===== 更新 =====


@router.put("/{user_id:uuid}", response_model=ResponseBase[UserResponse], summary="更新用户信息 (管理员)")
async def update_user(
    *,
    user_id: UUID,
    user_in: UserUpdate,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_UPDATE.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[UserResponse]:
    """
    管理员更新用户信息。

    允许具备权限的管理员修改任意用户的资料 (昵称、手机号、邮箱、状态等)。
    不包含密码修改 (请使用重置密码接口)。

    Args:
        user_id (UUID): 目标用户 ID。
        user_in (UserUpdate): 更新的用户数据。
        _ (User): 权限依赖（需要 user:update）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[UserResponse]: 更新后的用户信息。
    """
    user = await user_service.update_user(user_id=user_id, obj_in=user_in)
    return ResponseBase(data=UserResponse.model_validate(user), message="用户信息更新成功")


# ===== 批量删除 =====


@router.delete("/batch", response_model=ResponseBase[BatchOperationResult], summary="批量删除用户")
async def batch_delete_users(
    *,
    request: BatchDeleteRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_DELETE.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """
    批量删除用户。

    支持软删除和硬删除。需要用户-删除权限。

    Args:
        request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:delete）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。
    """
    result = await user_service.batch_delete_users(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(data=result)


# ===== 回收站 =====


@router.get("/recycle-bin", response_model=ResponseBase[PaginatedResponse[UserResponse]], summary="获取用户回收站列表")
async def get_recycle_bin(
    *,
    page: int = 1,
    page_size: int = 20,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_RECYCLE.value])),
    user_service: deps.UserServiceDep,
    keyword: str | None = None,
    is_superuser: bool | None = None,
    is_active: bool | None = None,
) -> ResponseBase[PaginatedResponse[UserResponse]]:
    """
    获取已删除的用户列表 (回收站)。
    需要用户-回收站权限。

    Args:
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        _ (User): 权限依赖（需要 user:recycle）。
        user_service (UserService): 用户服务依赖。
        keyword (str | None, optional): 关键词过滤. Defaults to None.
        is_superuser (bool | None, optional): 是否超级管理员过滤. Defaults to None.
        is_active (bool | None, optional): 是否启用过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[UserResponse]]: 分页后的用户列表。
    """
    users, total = await user_service.get_deleted_users(
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_superuser=is_superuser,
        is_active=is_active,
    )

    items = [
        UserResponse.model_validate(u).model_copy(update={"dept_name": u.dept.name if u.dept else None}) for u in users
    ]
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


# ===== 批量恢复 =====


@router.post("/batch/restore", response_model=ResponseBase[BatchOperationResult], summary="批量恢复用户")
async def batch_restore_users(
    *,
    request: BatchRestoreRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_RESTORE.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """批量恢复用户。

    从回收站中批量恢复软删除用户。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:restore）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """

    result = await user_service.batch_restore_users(ids=request.ids)
    return ResponseBase(data=result)


# ===== 单个恢复 =====


@router.post("/{user_id:uuid}/restore", response_model=ResponseBase[UserResponse], summary="恢复已删除用户")
async def restore_user(
    *,
    user_id: UUID,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_RESTORE.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[UserResponse]:
    """
    恢复已删除用户。

    从回收站中恢复指定用户。
    需要用户-恢复权限。

    Args:
        user_id (UUID): 目标用户 ID。
        _ (User): 权限依赖（需要 user:restore）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[UserResponse]: 恢复后的用户信息。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足时。
        NotFoundException: 用户不存在时。
    """
    user = await user_service.restore_user(id=user_id)
    return ResponseBase(data=UserResponse.model_validate(user), message="用户恢复成功")


# ===== 当前用户相关操作 =====


@router.get("/me", response_model=ResponseBase[UserResponse], summary="获取当前用户")
async def read_user_me(
    current_user: deps.CurrentUser,
) -> ResponseBase[UserResponse]:
    """
    获取当前用户信息。

    返回当前登录用户的详细信息。

    Args:
        current_user (User): 当前登录用户 (由依赖自动注入)。

    Returns:
        ResponseBase[UserResponse]: 当前用户的详细信息。
    """
    return ResponseBase(data=UserResponse.model_validate(current_user))


@router.put("/me", response_model=ResponseBase[UserResponse], summary="更新当前用户")
async def update_user_me(
    *,
    user_service: deps.UserServiceDep,
    user_in: UserMeUpdate,
    current_user: deps.CurrentUser,
) -> ResponseBase[UserResponse]:
    """
    更新当前用户信息。

    用户自行修改个人资料（如昵称、邮箱、手机号等）。

    Args:
        user_service (UserService): 用户服务依赖。
        user_in (UserUpdate): 用户更新数据。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[UserResponse]: 更新后的用户信息。
    """
    user = await user_service.update_user_me(user_id=current_user.id, obj_in=user_in)
    return ResponseBase(data=UserResponse.model_validate(user))


@router.put("/me/password", response_model=ResponseBase[UserResponse], summary="修改密码 (当前用户)")
async def change_password_me(
    *,
    user_service: deps.UserServiceDep,
    password_data: ChangePasswordRequest,
    current_user: deps.CurrentUser,
) -> ResponseBase[UserResponse]:
    """
    修改当前用户密码。

    需要验证旧密码是否正确。

    Args:
        user_service (UserService): 用户服务依赖。
        password_data (ChangePasswordRequest): 密码修改请求 (包含旧密码和新密码)。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[UserResponse]: 用户信息 (密码修改成功后)。
    """
    user = await user_service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    return ResponseBase(data=UserResponse.model_validate(user), message="密码修改成功")


# ===== 密码管理 =====


@router.put("/{user_id:uuid}/password", response_model=ResponseBase[UserResponse], summary="重置密码 (管理员)")
async def reset_user_password(
    *,
    user_id: UUID,
    password_data: ResetPasswordRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_PASSWORD_RESET.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[UserResponse]:
    """
    管理员重置用户密码。

    强制修改指定用户的密码，不需要知道旧密码。需要用户-重置密码权限。

    Args:
        user_id (UUID): 目标用户 ID。
        password_data (ResetPasswordRequest): 密码重置请求 (包含新密码)。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:password:reset）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[UserResponse]: 用户信息 (密码重置成功后)。
    """
    user = await user_service.reset_password(user_id=user_id, new_password=password_data.new_password)
    return ResponseBase(data=UserResponse.model_validate(user), message="密码重置成功")


# ===== 角色管理 =====


@router.get("/{user_id:uuid}/roles", response_model=ResponseBase[list[RoleResponse]], summary="获取用户角色")
async def get_user_roles(
    *,
    user_id: UUID,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_ROLES_LIST.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[list[RoleResponse]]:
    """
    获取用户已绑定的角色列表。

    Args:
        user_id (UUID): 目标用户 ID。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:roles:list）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[list[RoleResponse]]: 用户已绑定的角色列表。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。

    """

    roles = await user_service.get_user_roles(user_id=user_id)
    return ResponseBase(data=[RoleResponse.model_validate(r) for r in roles])


@router.put("/{user_id:uuid}/roles", response_model=ResponseBase[list[RoleResponse]], summary="设置用户角色")
async def set_user_roles(
    *,
    user_id: UUID,
    req: UserRolesUpdateRequest,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.USER_ROLES_UPDATE.value])),
    user_service: deps.UserServiceDep,
) -> ResponseBase[list[RoleResponse]]:
    """
    设置用户角色（全量覆盖，幂等）。

    Args:
        user_id (UUID): 目标用户 ID。
        req (UserRolesUpdateRequest): 用户角色更新请求体 (包含角色 ID 列表)。
        current_user (User): 当前登录用户。
        _ (User): 权限依赖（需要 user:roles:update）。
        user_service (UserService): 用户服务依赖。

    Returns:
        ResponseBase[list[RoleResponse]]: 用户已绑定的角色列表。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。

    """

    roles = await user_service.set_user_roles(user_id=user_id, role_ids=req.role_ids)
    return ResponseBase(data=[RoleResponse.model_validate(r) for r in roles], message="用户角色设置成功")
