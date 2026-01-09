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
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="状态筛选"),
) -> Any:
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
    audit = await service.get(audit_id)
    return ResponseBase(data={"id": str(audit.id), "name": audit.name, "scope": audit.scope, "result": audit.result})

