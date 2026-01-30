"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: logs.py
@DateTime: 2025-12-30 14:35:00
@Docs: 日志 API 接口 (Logs API).
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.permissions import PermissionCode
from app.features.import_export.logs import export_login_logs_df, export_operation_logs_df
from app.import_export import ImportExportService, delete_export_file
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.log import LoginLogResponse, OperationLogResponse

router = APIRouter(tags=["日志管理"])


@router.get("/login", response_model=ResponseBase[PaginatedResponse[LoginLogResponse]], summary="获取登录日志")
async def read_login_logs(
    current_user: deps.CurrentUser,
    log_service: deps.LogServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.LOG_LOGIN_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> ResponseBase[PaginatedResponse[LoginLogResponse]]:
    """
    获取登录日志 (分页)。

    查询系统登录日志记录，支持分页。按创建时间倒序排列。

    Args:
        current_user (User): 当前登录用户。
        log_service (LogService): 日志服务依赖。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[LoginLogResponse]]: 分页后的登录日志列表。
    """
    logs, total = await log_service.get_login_logs_paginated(page=page, page_size=page_size, keyword=keyword)
    return ResponseBase(
        data=PaginatedResponse(
            total=total, page=page, page_size=page_size, items=[LoginLogResponse.model_validate(log) for log in logs]
        )
    )


@router.get("/operation", response_model=ResponseBase[PaginatedResponse[OperationLogResponse]], summary="获取操作日志")
async def read_operation_logs(
    current_user: deps.CurrentUser,
    log_service: deps.LogServiceDep,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.LOG_OPERATION_LIST.value])),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> ResponseBase[PaginatedResponse[OperationLogResponse]]:
    """
    获取操作日志 (分页)。

    查询系统操作日志（API 调用记录），支持分页。按创建时间倒序排列。

    Args:
        current_user (User): 当前登录用户。
        log_service (LogService): 日志服务依赖。
        page (int, optional): 页码. Defaults to 1.
        page_size (int, optional): 每页数量. Defaults to 20.
        keyword (str | None, optional): 关键词过滤. Defaults to None.

    Returns:
        ResponseBase[PaginatedResponse[OperationLogResponse]]: 分页后的操作日志列表。
    """
    logs, total = await log_service.get_operation_logs_paginated(page=page, page_size=page_size, keyword=keyword)
    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[OperationLogResponse.model_validate(log) for log in logs],
        )
    )


@router.get(
    "/login/export",
    summary="导出登录日志",
)
async def export_login_logs(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.LOG_LOGIN_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出登录日志列表为 CSV/XLSX 文件。

    Args:
        db (Session): 数据库会话。
        current_user (User): 当前登录用户。
        fmt (str): 导出格式，csv 或 xlsx。

    Returns:
        FileResponse: 文件下载响应，后台自动清理临时文件。
    """
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="login_logs", df_fn=export_login_logs_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.get(
    "/operation/export",
    summary="导出操作日志",
)
async def export_operation_logs(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.LOG_OPERATION_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出操作日志列表为 CSV/XLSX 文件。

    Args:
        db (Session): 数据库会话。
        current_user (User): 当前登录用户。
        fmt (str): 导出格式，csv 或 xlsx。

    Returns:
        FileResponse: 文件下载响应，后台自动清理临时文件。
    """
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="operation_logs", df_fn=export_operation_logs_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )
