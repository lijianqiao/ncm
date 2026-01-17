"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: sessions.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话 API（在线用户/强制下线/踢人）。
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.permissions import PermissionCode
from app.features.import_export.sessions import export_sessions_df
from app.import_export import ImportExportService, delete_export_file
from app.schemas.common import BatchOperationResult, PaginatedResponse, ResponseBase
from app.schemas.session import KickUsersRequest, OnlineSessionResponse

router = APIRouter()


@router.get(
    "/online", response_model=ResponseBase[PaginatedResponse[OnlineSessionResponse]], summary="获取在线会话列表"
)
async def list_online_sessions(
    session_service: deps.SessionServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SESSION_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> ResponseBase[PaginatedResponse[OnlineSessionResponse]]:
    """
    获取在线会话列表，支持分页和搜索。
    需要 SESSION_LIST 权限。

    Args:
        session_service (SessionService): 在线会话服务依赖。
        current_user (User): 当前登录用户。
        page (int): 页码，默认值为 1。
        page_size (int): 每页数量，默认值为 20。
        keyword (str | None): 关键词过滤，支持用户名和 IP 搜索。

    Returns:
        ResponseBase[PaginatedResponse[OnlineSessionResponse]]: 包含在线会话列表的响应对象。

    Raises:
        CustomException: 当用户没有权限时抛出 403 错误。

    """
    items, total = await session_service.list_online(page=page, page_size=page_size, keyword=keyword)
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=items))


@router.post("/kick/batch", response_model=ResponseBase[BatchOperationResult], summary="批量强制下线")
async def kick_users(
    request: KickUsersRequest,
    session_service: deps.SessionServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SESSION_KICK.value])),
) -> Any:
    """
    批量强制下线指定用户列表。
    需要 SESSION_KICK 权限。

    Args:
        request (KickUsersRequest): 包含要强制下线的用户ID列表的请求体。
        session_service (SessionService): 在线会话服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[BatchOperationResult]: 包含操作结果的响应对象，包括成功数量和失败ID列表。

    Raises:
        CustomException: 当用户没有权限时抛出 403 错误。

    """
    success_count, failed_ids = await session_service.kick_users(user_ids=request.user_ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功下线 {success_count} 个用户" if not failed_ids else "部分下线成功",
        )
    )


@router.post("/kick/{user_id}", response_model=ResponseBase[None], summary="强制下线(踢人)")
async def kick_user(
    user_id: UUID,
    session_service: deps.SessionServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SESSION_KICK.value])),
) -> Any:
    """
    强制下线指定用户。
    需要 SESSION_KICK 权限。

    Args:
        user_id (UUID): 要强制下线的用户ID。
        session_service (SessionService): 在线会话服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[None]: 空响应对象，表示操作成功。

    Raises:
        CustomException: 当用户没有权限或用户不存在时抛出相应错误。

    """
    await session_service.kick_user(user_id=user_id)
    return ResponseBase(data=None, message="已强制下线")


@router.get(
    "/export",
    summary="导出在线会话",
)
async def export_sessions(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.SESSION_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出在线会话列表为 CSV/XLSX 文件。

    Args:
        db (Session): 数据库会话。
        current_user (User): 当前登录用户。
        fmt (str): 导出格式，csv 或 xlsx。

    Returns:
        FileResponse: 文件下载响应，后台自动清理临时文件。
    """
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="sessions", df_fn=export_sessions_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )
