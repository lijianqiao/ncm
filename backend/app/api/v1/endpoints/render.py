"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: render.py
@DateTime: 2026-01-09 23:00:00
@Docs: 配置渲染(Dry-Run) API。
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import DeviceCRUDDep, RenderServiceDep, SessionDep, TemplateServiceDep, require_permissions
from app.core.permissions import PermissionCode
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/render", tags=["配置渲染"])


class RenderRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict, description="模板参数")
    device_id: UUID | None = Field(default=None, description="用于上下文的设备ID(可选)")


class RenderResponse(BaseModel):
    rendered: str


@router.post(
    "/template/{template_id}",
    response_model=ResponseBase[RenderResponse],
    dependencies=[Depends(require_permissions([PermissionCode.RENDER_VIEW.value]))],
    summary="模板渲染预览(Dry-Run)",
)
async def render_template(
    template_id: UUID,
    body: RenderRequest,
    template_service: TemplateServiceDep,
    db: SessionDep,
    device_crud: DeviceCRUDDep,
    render_service: RenderServiceDep,
) -> ResponseBase[RenderResponse]:
    template = await template_service.get_template(template_id)

    device = None
    if body.device_id is not None:
        device = await device_crud.get(db, id=body.device_id)

    rendered = render_service.render(template, body.params, device=device)
    return ResponseBase(data=RenderResponse(rendered=rendered))

