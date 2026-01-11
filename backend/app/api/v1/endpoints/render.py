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

router = APIRouter(tags=["配置渲染"])


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
    """在下发前预览 Jinja2 模板渲染后的配置文本。

    支持传入空参数或模拟设备上下文（从设备表中提取属性）进行 Dry-Run。

    Args:
        template_id (UUID): 配置模板 ID。
        body (RenderRequest): 包含输入参数及可选设备上下文 ID 的请求。
        template_service (TemplateService): 模板管理服务。
        db (Session): 数据库会话。
        device_crud (CRUDDevice): 设备 CRUD 抽象。
        render_service (RenderService): 渲染逻辑核心服务。

    Returns:
        ResponseBase[RenderResponse]: 包含最终渲染出的配置字符串。
    """
    template = await template_service.get_template(template_id)

    device = None
    if body.device_id is not None:
        device = await device_crud.get(db, id=body.device_id)

    rendered = render_service.render(template, body.params, device=device)
    return ResponseBase(data=RenderResponse(rendered=rendered))
