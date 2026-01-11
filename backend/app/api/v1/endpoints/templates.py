"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: templates.py
@DateTime: 2026-01-09 23:00:00
@Docs: 模板库 API 接口。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, TemplateServiceDep, require_permissions
from app.core.enums import DeviceVendor, TemplateStatus, TemplateType
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.template import (
    TemplateCreate,
    TemplateNewVersionRequest,
    TemplateResponse,
    TemplateSubmitRequest,
    TemplateUpdate,
)

router = APIRouter(tags=["模板库"])


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[TemplateResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_LIST.value]))],
    summary="获取模板列表",
)
async def list_templates(
    service: TemplateServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    vendor: DeviceVendor | None = Query(default=None),
    template_type: TemplateType | None = Query(default=None),
    status: TemplateStatus | None = Query(default=None),
) -> ResponseBase[PaginatedResponse[TemplateResponse]]:
    """分页获取配置模板列表。

    Args:
        service (TemplateService): 模板服务依赖。
        page (int): 当前页码。
        page_size (int): 每页大小（1-100）。
        vendor (DeviceVendor | None): 按厂商过滤。
        template_type (TemplateType | None): 按模板类型过滤。
        status (TemplateStatus | None): 按状态过滤。

    Returns:
        ResponseBase[PaginatedResponse[TemplateResponse]]: 包含模板列表的分页响应。
    """
    items, total = await service.get_templates_paginated(
        page=page,
        page_size=page_size,
        vendor=vendor.value if vendor else None,
        template_type=template_type.value if template_type else None,
        status=status.value if status else None,
    )
    return ResponseBase(
        data=PaginatedResponse(
            items=[TemplateResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_CREATE.value]))],
    summary="创建模板(草稿)",
)
async def create_template(
    data: TemplateCreate,
    service: TemplateServiceDep,
    user: CurrentUser,
) -> ResponseBase[TemplateResponse]:
    """创建一个新的配置模板草稿。

    Args:
        data (TemplateCreate): 创建表单数据。
        service (TemplateService): 模板服务依赖。
        user (User): 创建者信息。

    Returns:
        ResponseBase[TemplateResponse]: 创建成功的模板信息。
    """
    template = await service.create_template(data, creator_id=user.id)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.get(
    "/{template_id}",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_LIST.value]))],
    summary="获取模板详情",
)
async def get_template(
    template_id: UUID,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponse]:
    """根据 ID 获取模板的详细定义信息。

    Args:
        template_id (UUID): 模板 ID。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 模板详情。
    """
    template = await service.get_template(template_id)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.put(
    "/{template_id}",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_UPDATE.value]))],
    summary="更新模板",
)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponse]:
    """更新处于草稿或拒绝状态的模板。

    Args:
        template_id (UUID): 模板 ID。
        data (TemplateUpdate): 要更新的字段。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 更新后的模板信息。
    """
    template = await service.update_template(template_id, data)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.post(
    "/{template_id}/new-version",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_CREATE.value]))],
    summary="创建新版本(草稿)",
)
async def new_version(
    template_id: UUID,
    body: TemplateNewVersionRequest,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponse]:
    """基于现有模板创建一个新的修订版本（初始为草稿）。

    Args:
        template_id (UUID): 源模板 ID。
        body (TemplateNewVersionRequest): 新版本的信息描述。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 新版本的模板详情。
    """
    template = await service.new_version(template_id, name=body.name, description=body.description)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.post(
    "/{template_id}/submit",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_SUBMIT.value]))],
    summary="提交模板审批",
)
async def submit_template(
    template_id: UUID,
    body: TemplateSubmitRequest,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponse]:
    """将草稿状态的模板提交至审批流程。

    Args:
        template_id (UUID): 模板 ID。
        body (TemplateSubmitRequest): 提交备注信息。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 更新状态后的模板详情。
    """
    template = await service.submit(template_id, comment=body.comment)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.delete(
    "/{template_id}",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="删除模板",
)
async def delete_template(template_id: UUID, service: TemplateServiceDep) -> ResponseBase[TemplateResponse]:
    """删除指定的模板。

    Args:
        template_id (UUID): 模板 ID。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 被删除的模板信息。
    """
    template = await service.delete_template(template_id)
    return ResponseBase(data=TemplateResponse.model_validate(template))
