"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: templates.py
@DateTime: 2026-01-09 23:00:00
@Docs: 模板库 API 接口。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.deps import CurrentUser, SessionDep, TemplateServiceDep, require_permissions
from app.core.config import settings
from app.core.enums import DeviceVendor, ParamType, TemplateStatus, TemplateType
from app.core.permissions import PermissionCode
from app.features.import_export.templates import export_templates_df
from app.import_export import ImportExportService, delete_export_file
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.template import (
    ExtractVariablesRequest,
    ExtractVariablesResponse,
    ParamTypeInfo,
    ParamTypeListResponse,
    TemplateApproveRequest,
    TemplateBatchRequest,
    TemplateBatchResult,
    TemplateCreate,
    TemplateCreateV2,
    TemplateNewVersionRequest,
    TemplateResponse,
    TemplateResponseV2,
    TemplateSubmitRequest,
    TemplateUpdate,
    TemplateUpdateV2,
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
    page_size: int = Query(default=20, ge=1, le=500),
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
    "/{template_id:uuid}",
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
    "/{template_id:uuid}",
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
    "/{template_id:uuid}/new-version",
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
    "/{template_id:uuid}/submit",
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
    template = await service.submit(template_id, comment=body.comment, approver_ids=body.approver_ids)
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.post(
    "/{template_id:uuid}/approve",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_APPROVE.value]))],
    summary="审批模板(某一级)",
)
async def approve_template(
    template_id: UUID,
    body: TemplateApproveRequest,
    service: TemplateServiceDep,
    user: CurrentUser,
) -> ResponseBase[TemplateResponse]:
    """对指定模板执行单级审批（支持三级串行审批）。

    三个审批级别依次进行，只有在前一等级通过后才可进入下一等级。
    审批通过到达最高等级后，模板状态将变更为“已批准”；若任一级拒绝，
    模板将回到“已拒绝”并记录审批备注。

    Args:
        template_id (UUID): 目标模板的唯一标识。
        body (TemplateApproveRequest): 审批请求体，包含审批等级、是否通过、备注。
        service (TemplateService): 模板服务依赖，用于执行业务流程。
        user (User): 当前审批人，用于审计和权限判断。

    Returns:
        ResponseBase[TemplateResponse]: 返回最新的模板详情（含状态与审批轨迹）。

    Raises:
        NotFoundException: 当模板不存在时。
        ForbiddenException: 当审批等级或审批人不具备操作权限时。
        ConflictException: 当模板状态不满足当前审批操作（如未提交或已终态）。
    """

    template = await service.approve_step(
        template_id,
        level=body.level,
        approve=body.approve,
        comment=body.comment,
        actor_user_id=user.id,
        is_superuser=user.is_superuser,
    )
    return ResponseBase(data=TemplateResponse.model_validate(template))


@router.delete(
    "/{template_id:uuid}",
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


@router.delete(
    "/batch",
    response_model=ResponseBase[TemplateBatchResult],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="批量删除模板",
)
async def batch_delete_templates(
    request: TemplateBatchRequest,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateBatchResult]:
    """批量软删除模板（可从回收站恢复）。

    Args:
        request (TemplateBatchRequest): 批量请求体，包含待删除模板的 ID 列表。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateBatchResult]: 返回批量操作结果（成功数、失败数、失败ID）。

    Raises:
        ForbiddenException: 当无删除权限或部分模板不允许删除时。
    """
    success_count, failed_ids = await service.batch_delete_templates(request.ids)
    return ResponseBase(
        data=TemplateBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量删除完成，成功 {success_count} 条",
    )


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[TemplateResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_LIST.value]))],
    summary="获取回收站模板列表",
)
async def read_recycle_bin_templates(
    service: TemplateServiceDep,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键字搜索"),
) -> ResponseBase[PaginatedResponse[TemplateResponse]]:
    """获取回收站中的模板（软删除后保留，可恢复）。

    Args:
        service (TemplateService): 模板服务依赖。
        page (int): 页码（从 1 开始）。
        page_size (int): 每页数量（1-500）。
        keyword (str | None): 关键字模糊匹配名称/描述。

    Returns:
        ResponseBase[PaginatedResponse[TemplateResponse]]: 回收站模板分页列表。
    """
    items, total = await service.get_recycle_bin_paginated(
        page=page,
        page_size=page_size,
        keyword=keyword,
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
    "/{template_id:uuid}/restore",
    response_model=ResponseBase[TemplateResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="恢复模板",
)
async def restore_template(
    template_id: UUID,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponse]:
    """从回收站恢复已删除的模板到原有状态。

    Args:
        template_id (UUID): 目标模板 ID。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponse]: 恢复后的模板详情。

    Raises:
        NotFoundException: 模板不存在或未处于可恢复状态时。
    """
    template = await service.restore_template(template_id)
    return ResponseBase(
        data=TemplateResponse.model_validate(template),
        message="模板已恢复",
    )


@router.post(
    "/batch/restore",
    response_model=ResponseBase[TemplateBatchResult],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="批量恢复模板",
)
async def batch_restore_templates(
    request: TemplateBatchRequest,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateBatchResult]:
    """批量恢复模板（从回收站恢复至正常状态）。

    Args:
        request (TemplateBatchRequest): 批量请求体，包含模板 ID 列表。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateBatchResult]: 批量恢复的结果统计。
    """
    success_count, failed_ids = await service.batch_restore_templates(request.ids)
    return ResponseBase(
        data=TemplateBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量恢复完成，成功 {success_count} 条",
    )


@router.delete(
    "/{template_id:uuid}/hard",
    response_model=ResponseBase[dict],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="彻底删除模板",
)
async def hard_delete_template(
    template_id: UUID,
    service: TemplateServiceDep,
) -> ResponseBase[dict]:
    """彻底删除模板（物理删除，不可恢复）。

    Args:
        template_id (UUID): 目标模板 ID。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[dict]: 操作结果消息。

    Raises:
        NotFoundException: 模板不存在时。
        ForbiddenException: 无权限或模板处于不可删除状态时。
    """
    await service.hard_delete_template(template_id)
    return ResponseBase(
        data={"message": "模板已彻底删除"},
        message="模板已彻底删除",
    )


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[TemplateBatchResult],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_DELETE.value]))],
    summary="批量彻底删除模板",
)
async def batch_hard_delete_templates(
    request: TemplateBatchRequest,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateBatchResult]:
    """批量彻底删除模板（物理删除，不可恢复）。

    Args:
        request (TemplateBatchRequest): 批量请求体，包含模板 ID 列表。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateBatchResult]: 批量硬删除的结果统计。
    """
    success_count, failed_ids = await service.batch_hard_delete_templates(request.ids)
    return ResponseBase(
        data=TemplateBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids,
        ),
        message=f"批量彻底删除完成，成功 {success_count} 条",
    )


@router.get(
    "/export",
    summary="导出模板库",
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_EXPORT.value]))],
)
async def export_templates(
    db: SessionDep,
    current_user: CurrentUser,
    fmt: str = Query("csv", pattern="^(csv|xlsx)$", description="导出格式"),
) -> FileResponse:
    """导出模板列表为 CSV/XLSX 文件。

    Args:
        db (Session): 数据库会话。
        current_user (User): 当前登录用户。
        fmt (str): 导出格式，csv 或 xlsx。

    Returns:
        FileResponse: 文件下载响应，后台自动清理临时文件。
    """
    svc = ImportExportService(db=db, redis_client=None, base_dir=str(settings.IMPORT_EXPORT_TMP_DIR or "") or None)
    result = await svc.export_table(fmt=fmt, filename_prefix="templates", df_fn=export_templates_df)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )


# ===== V2 表单化参数相关 API =====


# 参数类型元数据（静态数据）
_PARAM_TYPE_METADATA: list[ParamTypeInfo] = [
    ParamTypeInfo(
        value=ParamType.STRING.value,
        label="文本",
        description="普通文本字符串",
        has_options=False,
        has_range=False,
        has_pattern=True,
    ),
    ParamTypeInfo(
        value=ParamType.INTEGER.value,
        label="整数",
        description="整数数值",
        has_options=False,
        has_range=True,
        has_pattern=False,
    ),
    ParamTypeInfo(
        value=ParamType.BOOLEAN.value,
        label="布尔值",
        description="true/false 开关",
        has_options=False,
        has_range=False,
        has_pattern=False,
    ),
    ParamTypeInfo(
        value=ParamType.SELECT.value,
        label="下拉选择",
        description="从预定义选项中选择",
        has_options=True,
        has_range=False,
        has_pattern=False,
    ),
    ParamTypeInfo(
        value=ParamType.IP_ADDRESS.value,
        label="IP 地址",
        description="IPv4 或 IPv6 地址",
        has_options=False,
        has_range=False,
        has_pattern=True,
    ),
    ParamTypeInfo(
        value=ParamType.CIDR.value,
        label="CIDR",
        description="CIDR 格式地址（如 192.168.1.0/24）",
        has_options=False,
        has_range=False,
        has_pattern=True,
    ),
    ParamTypeInfo(
        value=ParamType.VLAN_ID.value,
        label="VLAN ID",
        description="VLAN 标识（1-4094）",
        has_options=False,
        has_range=True,
        has_pattern=False,
    ),
    ParamTypeInfo(
        value=ParamType.INTERFACE.value,
        label="接口名",
        description="网络接口名称（如 GigabitEthernet0/0/1）",
        has_options=False,
        has_range=False,
        has_pattern=True,
    ),
    ParamTypeInfo(
        value=ParamType.MAC_ADDRESS.value,
        label="MAC 地址",
        description="MAC 地址（如 00:1A:2B:3C:4D:5E）",
        has_options=False,
        has_range=False,
        has_pattern=True,
    ),
    ParamTypeInfo(
        value=ParamType.PORT.value,
        label="端口号",
        description="网络端口号（1-65535）",
        has_options=False,
        has_range=True,
        has_pattern=False,
    ),
]


@router.get(
    "/param-types",
    response_model=ResponseBase[ParamTypeListResponse],
    summary="获取参数类型列表",
)
async def get_param_types() -> ResponseBase[ParamTypeListResponse]:
    """获取所有可用的模板参数类型及其元数据。

    Returns:
        ResponseBase[ParamTypeListResponse]: 参数类型列表。
    """
    return ResponseBase(data=ParamTypeListResponse(types=_PARAM_TYPE_METADATA))


@router.post(
    "/extract-vars",
    response_model=ResponseBase[ExtractVariablesResponse],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_CREATE.value]))],
    summary="从模板内容提取变量",
)
async def extract_variables(
    request: ExtractVariablesRequest,
    service: TemplateServiceDep,
) -> ResponseBase[ExtractVariablesResponse]:
    """从 Jinja2 模板内容中自动提取变量并推断类型。

    Args:
        request (ExtractVariablesRequest): 包含模板内容的请求体。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[ExtractVariablesResponse]: 提取的变量列表及推断类型。
    """
    variables = service.auto_generate_parameters(request.content)
    raw_names = service.extract_variables(request.content)
    return ResponseBase(
        data=ExtractVariablesResponse(
            variables=variables,
            raw_names=raw_names,
        )
    )


@router.post(
    "/v2",
    response_model=ResponseBase[TemplateResponseV2],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_CREATE.value]))],
    summary="创建模板（V2 - 表单化参数）",
)
async def create_template_v2(
    data: TemplateCreateV2,
    service: TemplateServiceDep,
    user: CurrentUser,
) -> ResponseBase[TemplateResponseV2]:
    """创建一个新的配置模板草稿（使用表单化参数定义）。

    Args:
        data (TemplateCreateV2): 创建表单数据（含表单化参数列表）。
        service (TemplateService): 模板服务依赖。
        user (User): 创建者信息。

    Returns:
        ResponseBase[TemplateResponseV2]: 创建成功的模板信息（含参数列表）。
    """
    template = await service.create_template_v2(data, creator_id=user.id)
    return ResponseBase(data=TemplateResponseV2.model_validate(template))


@router.put(
    "/v2/{template_id:uuid}",
    response_model=ResponseBase[TemplateResponseV2],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_UPDATE.value]))],
    summary="更新模板（V2 - 表单化参数）",
)
async def update_template_v2(
    template_id: UUID,
    data: TemplateUpdateV2,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponseV2]:
    """更新模板（使用表单化参数定义）。

    Args:
        template_id (UUID): 模板 ID。
        data (TemplateUpdateV2): 更新数据（含表单化参数列表）。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponseV2]: 更新后的模板信息（含参数列表）。
    """
    template = await service.update_template_v2(template_id, data)
    return ResponseBase(data=TemplateResponseV2.model_validate(template))


@router.get(
    "/v2/{template_id:uuid}",
    response_model=ResponseBase[TemplateResponseV2],
    dependencies=[Depends(require_permissions([PermissionCode.TEMPLATE_LIST.value]))],
    summary="获取模板详情（V2 - 含参数列表）",
)
async def get_template_v2(
    template_id: UUID,
    service: TemplateServiceDep,
) -> ResponseBase[TemplateResponseV2]:
    """根据 ID 获取模板的详细定义信息（含表单化参数列表）。

    Args:
        template_id (UUID): 模板 ID。
        service (TemplateService): 模板服务依赖。

    Returns:
        ResponseBase[TemplateResponseV2]: 模板详情（含参数列表）。
    """
    template = await service.get_template(template_id)
    return ResponseBase(data=TemplateResponseV2.model_validate(template))
