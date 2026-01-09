"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alerts.py
@DateTime: 2026-01-10 04:05:00
@Docs: 告警 API 接口 (Alerts API).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.enums import AlertSeverity, AlertStatus, AlertType
from app.core.permissions import PermissionCode
from app.schemas.alert import AlertListQuery, AlertResponse
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter()


@router.get("/", response_model=ResponseBase[PaginatedResponse[AlertResponse]], summary="获取告警列表")
async def read_alerts(
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, description="关键词(标题/正文)"),
    alert_type: AlertType | None = Query(None, description="类型筛选"),
    severity: AlertSeverity | None = Query(None, description="级别筛选"),
    status: AlertStatus | None = Query(None, description="状态筛选"),
    related_device_id: UUID | None = Query(None, description="设备筛选"),
) -> ResponseBase[PaginatedResponse[AlertResponse]]:
    items, total = await alert_service.list_alerts(
        AlertListQuery(
            page=page,
            page_size=page_size,
            keyword=keyword,
            alert_type=alert_type,
            severity=severity,
            status=status,
            related_device_id=related_device_id,
        )
    )

    responses: list[AlertResponse] = []
    for a in items:
        resp = AlertResponse.model_validate(a)
        if a.related_device:
            resp.related_device_name = a.related_device.name
            resp.related_device_ip = a.related_device.ip_address
        responses.append(resp)

    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=responses,
        )
    )


@router.get("/{alert_id}", response_model=ResponseBase[AlertResponse], summary="获取告警详情")
async def read_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
) -> ResponseBase[AlertResponse]:
    alert = await alert_service.get_alert(alert_id)
    resp = AlertResponse.model_validate(alert)
    if alert.related_device:
        resp.related_device_name = alert.related_device.name
        resp.related_device_ip = alert.related_device.ip_address
    return ResponseBase(data=resp)


@router.post("/{alert_id}/ack", response_model=ResponseBase[AlertResponse], summary="确认告警")
async def ack_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_ACK.value])),
) -> ResponseBase[AlertResponse]:
    alert = await alert_service.ack_alert(alert_id)
    resp = AlertResponse.model_validate(alert)
    if alert.related_device:
        resp.related_device_name = alert.related_device.name
        resp.related_device_ip = alert.related_device.ip_address
    return ResponseBase(data=resp)


@router.post("/{alert_id}/close", response_model=ResponseBase[AlertResponse], summary="关闭告警")
async def close_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_CLOSE.value])),
) -> ResponseBase[AlertResponse]:
    alert = await alert_service.close_alert(alert_id)
    resp = AlertResponse.model_validate(alert)
    if alert.related_device:
        resp.related_device_name = alert.related_device.name
        resp.related_device_ip = alert.related_device.ip_address
    return ResponseBase(data=resp)
