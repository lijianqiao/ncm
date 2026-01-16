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
from app.schemas.alert import AlertListQuery, AlertResponse
from app.schemas.common import PaginatedResponse, ResponseBase

router = APIRouter()


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
    """获取分页过滤的告警列表。

    根据提供的关键词、告警类型、严重程度、状态以及关联设备 ID 进行筛选，返回分页后的告警列表。

    Args:
        alert_service (AlertService): 告警服务依赖。
        current_user (User): 当前登录用户。
        page (int): 请求的页码，从 1 开始。默认为 1。
        page_size (int): 每页显示的记录数。默认为 20。
        keyword (str | None): 搜索关键词，匹配告警标题或正文。
        alert_type (AlertType | None): 告警类型筛选。
        severity (AlertSeverity | None): 告警严重程度筛选。
        status (AlertStatus | None): 告警状态筛选。
        related_device_id (UUID | None): 关联的设备 ID 筛选。

    Returns:
        ResponseBase[PaginatedResponse[AlertResponse]]: 包含分页后的告警数据及其总数的响应。
    """
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
    """根据 ID 获取单个告警的详细信息。

    Args:
        alert_id (UUID): 告警的主键 ID。
        alert_service (AlertService): 告警服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[AlertResponse]: 包含告警详情数据的响应。
    """
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
    """确认指定的告警。

    将被选中的告警状态更新为“已确认”，并记录处理人信息。

    Args:
        alert_id (UUID): 告警的主键 ID。
        alert_service (AlertService): 告警服务依赖。
        current_user (User): 当前执行确认操作的用户。

    Returns:
        ResponseBase[AlertResponse]: 更新状态后的告警详情。
    """
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
    """关闭指定的告警。

    将被选中的告警状态更新为“已关闭”，表示告警已处理完毕或已恢复。

    Args:
        alert_id (UUID): 告警的主键 ID。
        alert_service (AlertService): 告警服务依赖。
        current_user (User): 当前执行关闭操作的用户。

    Returns:
        ResponseBase[AlertResponse]: 状态更新后的告警详情。
    """
    alert = await alert_service.close_alert(alert_id)
    resp = AlertResponse.model_validate(alert)
    if alert.related_device:
        resp.related_device_name = alert.related_device.name
        resp.related_device_ip = alert.related_device.ip_address
    return ResponseBase(data=resp)


@router.post("/batch/ack", response_model=ResponseBase[dict], summary="批量确认告警")
async def batch_ack_alerts(
    alert_ids: list[UUID],
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_ACK.value])),
) -> ResponseBase[dict]:
    """批量确认告警。

    Args:
        alert_ids: 告警 ID 列表。
        alert_service: 告警服务依赖。
        current_user: 当前用户。

    Returns:
        ResponseBase[dict]: 批量操作结果 {"success": 数量, "failed": 数量}。
    """
    result = await alert_service.batch_ack_alerts(alert_ids)
    return ResponseBase(data=result)


@router.post("/batch/close", response_model=ResponseBase[dict], summary="批量关闭告警")
async def batch_close_alerts(
    alert_ids: list[UUID],
    alert_service: deps.AlertServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.ALERT_CLOSE.value])),
) -> ResponseBase[dict]:
    """批量关闭告警。

    Args:
        alert_ids: 告警 ID 列表。
        alert_service: 告警服务依赖。
        current_user: 当前用户。

    Returns:
        ResponseBase[dict]: 批量操作结果 {"success": 数量, "failed": 数量}。
    """
    result = await alert_service.batch_close_alerts(alert_ids)
    return ResponseBase(data=result)
