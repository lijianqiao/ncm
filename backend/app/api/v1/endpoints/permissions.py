"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: permissions.py
@DateTime: 2026-01-06 00:00:00
@Docs: 权限字典 API（用于前端选择/绑定权限码）。
"""

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.permissions import PermissionCode
from app.schemas.common import ResponseBase
from app.schemas.permission import PermissionDictItem

router = APIRouter(tags=["权限管理"])


@router.get("/", response_model=ResponseBase[list[PermissionDictItem]], summary="获取权限字典")
async def list_permissions(
    current_user: deps.CurrentUser,
    permission_service: deps.PermissionServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.MENU_OPTIONS_LIST.value])),
) -> ResponseBase[list[PermissionDictItem]]:
    """获取系统权限字典（权限码以代码为源）。

    前端用于菜单/角色管理时的“权限码选择”，避免手动输入权限字符串。

    Args:
        current_user (User): 当前登录用户。
        permission_service (PermissionService): 权限字典服务依赖。
        _ (User): 权限依赖（需要 menu:options:list）。

    Returns:
        ResponseBase[list[PermissionDictItem]]: 权限字典列表。

    Raises:
        UnauthorizedException: 未登录或令牌无效时。
        ForbiddenException: 权限不足时。
    """

    items = await permission_service.list_permissions()
    return ResponseBase(data=items)
