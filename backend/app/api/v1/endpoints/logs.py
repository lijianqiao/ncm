"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: logs.py
@DateTime: 2025-12-30 14:35:00
@Docs: 日志 API 接口 (Logs API).
"""

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.log import LoginLogResponse, OperationLogResponse

router = APIRouter()


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
