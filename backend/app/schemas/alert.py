"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert.py
@DateTime: 2026-01-10 03:15:00
@Docs: 告警 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AlertSeverity, AlertStatus, AlertType


class AlertCreate(BaseModel):
    """创建告警请求体（内部使用）。"""

    alert_type: AlertType = Field(default=AlertType.CONFIG_CHANGE, description="告警类型")
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM, description="告警级别")
    title: str = Field(..., min_length=1, max_length=200, description="告警标题")
    message: str | None = Field(default=None, description="告警正文")
    details: dict | None = Field(default=None, description="告警详情(JSON)")
    source: str | None = Field(default=None, max_length=50, description="告警来源(diff/discovery/manual)")
    related_device_id: UUID | None = Field(default=None, description="关联设备ID")
    related_discovery_id: UUID | None = Field(default=None, description="关联发现记录ID")


class AlertUpdate(BaseModel):
    """更新告警（内部使用）。"""

    status: AlertStatus | None = Field(default=None, description="告警状态")
    severity: AlertSeverity | None = Field(default=None, description="告警级别")
    title: str | None = Field(default=None, max_length=200, description="告警标题")
    message: str | None = Field(default=None, description="告警正文")
    details: dict | None = Field(default=None, description="告警详情(JSON)")
    # 操作人信息
    acked_by_id: UUID | None = Field(default=None, description="确认人ID")
    acked_at: datetime | None = Field(default=None, description="确认时间")
    closed_by_id: UUID | None = Field(default=None, description="关闭人ID")
    closed_at: datetime | None = Field(default=None, description="关闭时间")


class AlertResponse(BaseModel):
    """告警响应。"""

    id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: str | None = None
    details: dict | None = None
    source: str | None = None
    related_device_id: UUID | None = None
    related_discovery_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    # 关联信息（便于展示）
    related_device_name: str | None = None
    related_device_ip: str | None = None

    # 确认人信息
    acked_by_id: UUID | None = None
    acked_by_username: str | None = None
    acked_by_nickname: str | None = None
    acked_by_display: str | None = None
    acked_at: datetime | None = None

    # 关闭人信息
    closed_by_id: UUID | None = None
    closed_by_username: str | None = None
    closed_by_nickname: str | None = None
    closed_by_display: str | None = None
    closed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertListQuery(BaseModel):
    """告警列表查询。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=500, description="每页数量")
    keyword: str | None = Field(default=None, description="关键词(标题/正文)")
    alert_type: AlertType | None = Field(default=None, description="类型筛选")
    severity: AlertSeverity | None = Field(default=None, description="级别筛选")
    status: AlertStatus | None = Field(default=None, description="状态筛选")
    related_device_id: UUID | None = Field(default=None, description="设备筛选")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")


class AlertStats(BaseModel):
    """告警统计数据。"""

    total: int = Field(..., description="告警总数")
    by_type: dict[str, int] = Field(default_factory=dict, description="按类型分组")
    by_severity: dict[str, int] = Field(default_factory=dict, description="按级别分组")
    by_status: dict[str, int] = Field(default_factory=dict, description="按状态分组")


class AlertTrendItem(BaseModel):
    """告警趋势单项。"""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    count: int = Field(..., description="当日新增数量")


class AlertTrend(BaseModel):
    """告警趋势数据。"""

    days: int = Field(..., description="统计天数")
    items: list[AlertTrendItem] = Field(default_factory=list, description="趋势列表")
