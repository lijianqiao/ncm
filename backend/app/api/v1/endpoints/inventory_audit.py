"""
@Author: li
@Email: lij
@FileName: inventory_audit.py
@DateTime: 2026-01-09 21:30:00
@Docs: 资产盘点 API。
"""

from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.inventory_audit import InventoryAuditCreate, InventoryAuditResponse

router = APIRouter()


@router.post(
    "/",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="创建盘点任务（异步执行）",
)
async def create_inventory_audit(
    body: InventoryAuditCreate,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_CREATE.value])),
) -> Any:
    """提交一个资产盘点任务。

    接口会立即创建记录并触发 Celery 异步扫描，识别在线、离线、影子资产以及配置不一致设备。

    Args:
        body (InventoryAuditCreate): 盘点配置，包括名称和审计范围（网段或部门）。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 任务创建人。

    Returns:
        ResponseBase[InventoryAuditResponse]: 包含创建记录及其绑定的 Celery 任务 ID。
    """
    audit = await service.create(body, operator_id=current_user.id)

    from app.celery.tasks.inventory_audit import run_inventory_audit

    celery_result = cast(Any, run_inventory_audit).delay(audit_id=str(audit.id))  # type: ignore[attr-defined]
    audit = await service.bind_celery_task(audit.id, celery_task_id=celery_result.id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit))


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[InventoryAuditResponse]],
    summary="盘点任务列表",
)
async def list_inventory_audits(
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    status: str | None = Query(default=None, description="状态筛选"),
) -> ResponseBase[PaginatedResponse[InventoryAuditResponse]]:
    """获取所有历史和正在进行的资产盘点任务记录。

    Args:
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。
        page (int): 页码。
        page_size (int): 每页限制。
        status (str | None): 任务状态过滤。

    Returns:
        ResponseBase[PaginatedResponse[InventoryAuditResponse]]: 分页盘点记录。
    """
    items, total = await service.list_paginated(page=page, page_size=page_size, status=status)
    return ResponseBase(
        data=PaginatedResponse(
            items=[InventoryAuditResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{audit_id}",
    response_model=ResponseBase[InventoryAuditResponse],
    summary="盘点任务详情",
)
async def get_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
) -> Any:
    """获取指定盘点任务的执行结果摘要。

    Args:
        audit_id (UUID): 盘点任务 UUID。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[InventoryAuditResponse]: 包含审计统计及分析报告的数据详情。
    """
    audit = await service.get(audit_id)
    return ResponseBase(data=InventoryAuditResponse.model_validate(audit))


@router.get(
    "/{audit_id}/export",
    response_model=ResponseBase[dict],
    summary="导出盘点报告(JSON)",
)
async def export_inventory_audit(
    audit_id: UUID,
    service: deps.InventoryAuditServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.INVENTORY_AUDIT_VIEW.value])),
) -> Any:
    """以 JSON 结构获取盘点审计的完整详单。

    Args:
        audit_id (UUID): 任务 ID。
        service (InventoryAuditService): 资产盘点服务。
        current_user (User): 授权用户。

    Returns:
        ResponseBase[dict]: 包含范围、匹配明细、差异资产列表的原始数据。
    """
    audit = await service.get(audit_id)
    return ResponseBase(data={"id": str(audit.id), "name": audit.name, "scope": audit.scope, "result": audit.result})
