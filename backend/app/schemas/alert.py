"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alert.py
@DateTime: 2026-01-10 03:15:00
@Docs: 告警 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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

    class Config:
        from_attributes = True


class AlertListQuery(BaseModel):
    """告警列表查询。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    keyword: str | None = Field(default=None, description="关键词(标题/正文)")
    alert_type: AlertType | None = Field(default=None, description="类型筛选")
    severity: AlertSeverity | None = Field(default=None, description="级别筛选")
    status: AlertStatus | None = Field(default=None, description="状态筛选")
    related_device_id: UUID | None = Field(default=None, description="设备筛选")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")

