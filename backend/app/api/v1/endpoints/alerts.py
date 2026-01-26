"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: alerts.py
@DateTime: 2026-01-10 04:05:00
@Docs: 告警 API 接口 (Alerts API).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api import deps
from app.core.config import settings
from app.core.enums import AlertSeverity, AlertStatus, AlertType
from app.core.permissions import PermissionCode
from app.features.import_export.alerts import export_alerts_df
from app.import_export import ImportExportService, delete_export_file
from app.models.alert import Alert
from app.schemas.alert import AlertListQuery, AlertResponse, AlertStats, AlertTrend, AlertTrendItem
from app.schemas.common import BatchOperationResult, PaginatedResponse, ResponseBase
from app.utils.user_display import format_user_display_name

router = APIRouter()


def _build_alert_response(alert: Alert) -> AlertResponse:
    """
    将 Alert 模型转换为响应 Schema。

    Args:
        alert: Alert 模型对象

    Returns:
        AlertResponse: 告警响应 Schema
    """
    resp = AlertResponse.model_validate(alert)

    # 关联设备信息
    if alert.related_device:
        resp.related_device_name = alert.related_device.name
        resp.related_device_ip = alert.related_device.ip_address

    # 确认人信息
    if alert.acked_by:
        resp.acked_by_id = alert.acked_by_id
        resp.acked_by_username = alert.acked_by.username
        resp.acked_by_nickname = alert.acked_by.nickname
        resp.acked_by_display = format_user_display_name(alert.acked_by.nickname, alert.acked_by.username)
        resp.acked_at = alert.acked_at

    # 关闭人信息
    if alert.closed_by:
        resp.closed_by_id = alert.closed_by_id
        resp.closed_by_username = alert.closed_by.username
        resp.closed_by_nickname = alert.closed_by.nickname
        resp.closed_by_display = format_user_display_name(alert.closed_by.nickname, alert.closed_by.username)
        resp.closed_at = alert.closed_at

    return resp


@router.get("/", response_model=ResponseBase[PaginatedResponse[AlertResponse]], summary="获取告警列表")
async def read_alerts(
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键词(标题/正文)"),
    alert_type: AlertType | None = Query(None, description="类型筛选"),
    severity: AlertSeverity | None = Query(None, description="级别筛选"),
    status: AlertStatus | None = Query(None, description="状态筛选"),
    related_device_id: UUID | None = Query(None, description="设备筛选"),
) -> ResponseBase[PaginatedResponse[AlertResponse]]:
    """获取分页过滤的告警列表。"""
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

    responses = [_build_alert_response(a) for a in items]

    return ResponseBase(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=responses,
        )
    )


@router.get(
    "/export",
    summary="导出告警列表",
)
async def export_alerts(
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_EXPORT.value])),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出告警列表为 CSV/XLSX 文件。"""
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="alerts", df_fn=export_alerts_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


@router.get("/{alert_id}", response_model=ResponseBase[AlertResponse], summary="获取告警详情")
async def read_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
) -> ResponseBase[AlertResponse]:
    """根据 ID 获取单个告警的详细信息。"""
    alert = await alert_service.get_alert(alert_id)
    return ResponseBase(data=_build_alert_response(alert))


@router.post("/{alert_id}/ack", response_model=ResponseBase[AlertResponse], summary="确认告警")
async def ack_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_ACK.value])),
) -> ResponseBase[AlertResponse]:
    """确认指定的告警，并记录操作人信息。"""
    alert = await alert_service.ack_alert(alert_id, user_id=current_user.id)
    return ResponseBase(data=_build_alert_response(alert))


@router.post("/{alert_id}/close", response_model=ResponseBase[AlertResponse], summary="关闭告警")
async def close_alert(
    alert_id: UUID,
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_CLOSE.value])),
) -> ResponseBase[AlertResponse]:
    """关闭指定的告警，并记录操作人信息。"""
    alert = await alert_service.close_alert(alert_id, user_id=current_user.id)
    return ResponseBase(data=_build_alert_response(alert))


@router.post("/batch/ack", response_model=ResponseBase[BatchOperationResult], summary="批量确认告警")
async def batch_ack_alerts(
    alert_ids: list[UUID],
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_ACK.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量确认告警。"""
    result = await alert_service.batch_ack_alerts(alert_ids, user_id=current_user.id)
    return ResponseBase(data=result)


@router.post("/batch/close", response_model=ResponseBase[BatchOperationResult], summary="批量关闭告警")
async def batch_close_alerts(
    alert_ids: list[UUID],
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_CLOSE.value])),
) -> ResponseBase[BatchOperationResult]:
    """批量关闭告警。"""
    result = await alert_service.batch_close_alerts(alert_ids, user_id=current_user.id)
    return ResponseBase(data=result)


# ===== 统计接口 =====


@router.get("/stats", response_model=ResponseBase[AlertStats], summary="获取告警统计")
async def get_alert_stats(
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
) -> ResponseBase[AlertStats]:
    """获取告警统计数据（按类型/级别/状态分组）。"""
    stats = await alert_service.get_stats()
    return ResponseBase(data=AlertStats(**stats))


@router.get("/trend", response_model=ResponseBase[AlertTrend], summary="获取告警趋势")
async def get_alert_trend(
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_LIST.value])),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
) -> ResponseBase[AlertTrend]:
    """获取告警趋势数据（近 N 天每日新增）。"""
    trend_data = await alert_service.get_trend(days=days)
    items = [AlertTrendItem(**item) for item in trend_data]
    return ResponseBase(data=AlertTrend(days=days, items=items))
