"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dashboard.py
@DateTime: 2025-12-30 22:20:00
@Docs: 仪表盘 API 接口.
"""

from fastapi import APIRouter

from app.api import deps
from app.schemas.common import ResponseBase
from app.schemas.dashboard import DashboardStats

router = APIRouter()


@router.get("/summary", response_model=ResponseBase[DashboardStats], summary="获取仪表盘统计")
async def get_dashboard_summary(
    current_user: deps.CurrentUser,
    service: deps.DashboardServiceDep,
) -> ResponseBase[DashboardStats]:
    """
    获取仪表盘统计数据。

    聚合查询用户、角色、菜单的总量，以及今日登录/操作次数、近七日登录趋势和最新登录记录。
    数据用于前端仪表盘首页展示。

    Args:
        current_user (User): 当前登录用户。
        service (DashboardService): 仪表盘服务依赖。

    Returns:
        ResponseBase[DashboardStats]: 包含各项统计指标的响应对象。
    """
    stats = await service.get_summary_stats(current_user=current_user)
    return ResponseBase(data=stats)
