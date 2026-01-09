"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dashboard.py
@DateTime: 2025-12-30 22:05:00
@Docs: 仪表盘 Dashboard 相关 Schema 定义。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoginLogSimple(BaseModel):
    """
    简化的登录日志展示 (用于仪表盘列表).
    """

    id: Any
    username: str
    ip: str | None = None
    address: str | None = None
    browser: str | None = None
    os: str | None = None
    status: bool
    msg: str | None = None
    created_at: Any

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    """
    仪表盘聚合统计数据。
    """

    # 核心计数
    # 超级管理员可见：全局统计
    total_users: int | None = Field(None, description="全局用户总数（超级管理员可见）")
    active_users: int | None = Field(None, description="全局活跃用户数（超级管理员可见）")
    total_roles: int | None = Field(None, description="全局角色总数（超级管理员可见）")
    total_menus: int | None = Field(None, description="全局菜单总数（超级管理员可见）")

    # 今日动态
    today_login_count: int | None = Field(None, description="今日全局登录次数（超级管理员可见）")
    today_operation_count: int | None = Field(None, description="今日全局操作次数（超级管理员可见）")

    # 趋势 (近7日)
    # 格式: [{"date": "2024-01-01", "count": 10}, ...]
    login_trend: list[dict[str, Any]] = Field(default_factory=list, description="全局登录趋势（超级管理员可见）")

    # 最新动态
    recent_logins: list[LoginLogSimple] = Field(default_factory=list, description="全局最近登录（超级管理员可见）")

    # 普通用户可见：个人维度
    my_today_login_count: int = Field(0, description="我今日登录次数")
    my_today_operation_count: int = Field(0, description="我今日操作次数")
    my_login_trend: list[dict[str, Any]] = Field(default_factory=list, description="我近7日登录趋势")
    my_recent_logins: list[LoginLogSimple] = Field(default_factory=list, description="我最近登录记录")
