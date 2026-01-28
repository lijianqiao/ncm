"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy.py
@DateTime: 2026-01-09 23:45:00
@Docs: 安全批量下发 API。

路由顺序规则（重要）:
    FastAPI 按定义顺序匹配路由，静态路由必须在动态路由之前定义。
    
    1. 根路由: `/` (GET 列表, POST 创建)
    2. 静态路由: `/recycle-bin`, `/batch`, `/batch/restore`, `/batch/hard`
    3. 动态路由: `/{task_id:uuid}`, `/{task_id:uuid}/approve`, `/{task_id:uuid}/execute` 等
    
    错误示例: 如果 `/{task_id:uuid}` 在 `/recycle-bin` 之前定义，
    访问 `/recycle-bin` 时会被 `/{task_id:uuid}` 错误匹配。
"""

from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api import deps
from app.api.deps import CurrentUser, DeployServiceDep, require_permissions
from app.core.enums import TaskStatus
from app.core.otp_notice import build_otp_required_response
from app.core.permissions import PermissionCode
from app.schemas.common import (
    BatchDeleteRequest,
    BatchOperationResult,
    BatchRestoreRequest,
    PaginatedResponse,
    ResponseBase,
)
from app.schemas.deploy import (
    DeployApproveRequest,
    DeployCreateRequest,
    DeployRollbackResponse,
    DeployTaskResponse,
    RollbackPreviewResponse,
)

router = APIRouter(tags=["安全批量下发"])


# ==============================================================================
# 1. 根路由 - Root Routes
# ==============================================================================


@router.get(
    "/",
    response_model=ResponseBase[PaginatedResponse[DeployTaskResponse]],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_VIEW.value]))],
    summary="下发任务列表（复用 Task 表）",
)
async def list_deploy_tasks(
    service: DeployServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> ResponseBase[PaginatedResponse[DeployTaskResponse]]:
    """获取所有批量配置下发任务的列表。

    Args:
        service (DeployService): 下发服务依赖。
        page (int): 当前页码。
        page_size (int): 每页限制数量。

    Returns:
        ResponseBase[PaginatedResponse[DeployTaskResponse]]: 分页后的任务概览。
    """
    items, total = await service.list_tasks_paginated(page=page, page_size=page_size)
    return ResponseBase(
        data=PaginatedResponse(
            items=[DeployTaskResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_CREATE.value]))],
    summary="创建下发任务",
)
async def create_deploy_task(
    body: DeployCreateRequest,
    service: DeployServiceDep,
    user: CurrentUser,
) -> ResponseBase[DeployTaskResponse]:
    """创建批量设备配置下发任务。

    通过指定渲染后的配置内容和目标设备，并在正式下发前创建多级审批流。

    Args:
        body (DeployCreateRequest): 包含任务名称、描述、目标设备及下发内容的请求。
        service (DeployService): 下发服务依赖。
        user (User): 任务提交人。

    Returns:
        ResponseBase[DeployTaskResponse]: 包含初始状态及审批进度的任务详情。
    """
    task = await service.create_deploy_task(body, submitter_id=user.id)
    return ResponseBase(data=DeployTaskResponse.model_validate(task))


# ==============================================================================
# 2. 静态路由 - Static Routes (必须在动态路由之前)
# ==============================================================================


@router.get(
    "/recycle-bin",
    response_model=ResponseBase[PaginatedResponse[DeployTaskResponse]],
    dependencies=[
        Depends(deps.get_current_active_superuser),
        Depends(require_permissions([PermissionCode.DEPLOY_RECYCLE.value])),
    ],
    summary="下发任务回收站列表",
)
async def list_deploy_tasks_recycle_bin(
    service: DeployServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> ResponseBase[PaginatedResponse[DeployTaskResponse]]:
    """获取已删除的下发任务列表（回收站）。

    仅超级管理员可查看，用于审计与批量恢复。

    Args:
        service (DeployService): 下发服务依赖。
        page (int): 页码（从 1 开始）。
        page_size (int): 每页数量（1-500）。

    Returns:
        ResponseBase[PaginatedResponse[DeployTaskResponse]]: 回收站任务分页列表。
    """
    items, total = await service.list_deleted_tasks_paginated(page=page, page_size=page_size)
    return ResponseBase(
        data=PaginatedResponse(
            items=[DeployTaskResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.delete(
    "/batch",
    response_model=ResponseBase[BatchOperationResult],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_DELETE.value]))],
    summary="批量删除下发任务",
)
async def batch_delete_deploy_tasks(
    request: BatchDeleteRequest,
    service: DeployServiceDep,
    user: CurrentUser,
) -> ResponseBase[BatchOperationResult]:
    """批量删除下发任务（支持软/硬删除）。

    当 `hard_delete` 为 True 时执行物理删除，不可恢复；否则为软删除，可在回收站恢复。

    Args:
        request (BatchDeleteRequest): 批量删除请求体（包含 ID 列表与是否硬删除）。
        service (DeployService): 下发服务依赖。
        user (User): 操作人信息。

    Returns:
        ResponseBase[BatchOperationResult]: 批量操作结果（成功数与失败ID）。
    """
    result = await service.batch_delete_tasks(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(data=result)


@router.post(
    "/batch/restore",
    response_model=ResponseBase[BatchOperationResult],
    dependencies=[
        Depends(deps.get_current_active_superuser),
        Depends(require_permissions([PermissionCode.DEPLOY_RESTORE.value])),
    ],
    summary="批量恢复下发任务",
)
async def batch_restore_deploy_tasks(
    request: BatchRestoreRequest,
    service: DeployServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """批量恢复已删除的下发任务（从回收站恢复）。

    Args:
        request (BatchRestoreRequest): 批量恢复请求体（包含 ID 列表）。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量恢复结果。
    """
    result = await service.batch_restore_tasks(ids=request.ids)
    return ResponseBase(data=result)


@router.delete(
    "/batch/hard",
    response_model=ResponseBase[BatchOperationResult],
    dependencies=[
        Depends(deps.get_current_active_superuser),
        Depends(require_permissions([PermissionCode.DEPLOY_DELETE.value])),
    ],
    summary="批量彻底删除下发任务",
)
async def batch_hard_delete_deploy_tasks(
    request: BatchDeleteRequest,
    service: DeployServiceDep,
) -> ResponseBase[BatchOperationResult]:
    """批量彻底删除任务（物理删除，不可恢复）。

    Args:
        request (BatchDeleteRequest): 批量请求体（包含 ID 列表）。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[BatchOperationResult]: 批量硬删除结果。
    """
    result = await service.batch_delete_tasks(ids=request.ids, hard_delete=True)
    return ResponseBase(data=result)


# ==============================================================================
# 3. 动态路由 - Dynamic Routes (/{task_id:uuid}/...)
# ==============================================================================


@router.get(
    "/{task_id:uuid}",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_VIEW.value]))],
    summary="下发任务详情",
)
async def get_deploy_task(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse] | JSONResponse:
    """获取下发任务的完整详细信息。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployTaskResponse]: 包含设备下发日志及状态的详细数据。
    """
    task = await service.get_task(task_id)
    data = DeployTaskResponse.model_validate(task)
    data.device_results = await service.get_device_results(task)
    if data.result and data.result.get("otp_required"):
        return build_otp_required_response(
            message=data.error_message or "需要重新输入 OTP 验证码",
            details={
                "otp_required": True,
                "otp_required_groups": data.result.get("otp_required_groups"),
                "expires_in": data.result.get("expires_in"),
                "next_action": data.result.get("next_action"),
            },
        )
    return ResponseBase(data=data)


@router.delete(
    "/{task_id:uuid}",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_DELETE.value]))],
    summary="删除下发任务",
)
async def delete_deploy_task(
    task_id: UUID,
    service: DeployServiceDep,
    user: CurrentUser,
) -> ResponseBase[DeployTaskResponse]:
    """删除单个下发任务（软删除）。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。
        user (User): 操作人信息。

    Returns:
        ResponseBase[DeployTaskResponse]: 被标记删除后的任务详情。
    """
    task = await service.delete_task(task_id=task_id)
    return ResponseBase(data=DeployTaskResponse.model_validate(task), message="下发任务删除成功")


@router.post(
    "/{task_id:uuid}/approve",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_APPROVE.value]))],
    summary="审批(某一级)",
)
async def approve_task(
    task_id: UUID,
    body: DeployApproveRequest,
    service: DeployServiceDep,
    user: CurrentUser,
) -> ResponseBase[DeployTaskResponse]:
    """对指定的下发任务进行单级审批操作。

    支持多级审批逻辑。如果所有级别均已通过，任务状态将更新为"已审批"。

    Args:
        task_id (UUID): 任务 ID。
        body (DeployApproveRequest): 包含审批级别、审批结论 (通过/拒绝) 及意见。
        service (DeployService): 下发服务依赖。
        user (User): 当前审批人。

    Returns:
        ResponseBase[DeployTaskResponse]: 更新后的任务及审批进度。
    """
    task = await service.approve_step(
        task_id,
        level=body.level,
        approve=body.approve,
        comment=body.comment,
        actor_user_id=user.id,
        is_superuser=user.is_superuser,
    )
    return ResponseBase(data=DeployTaskResponse.model_validate(task))


@router.post(
    "/{task_id:uuid}/execute",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_EXECUTE.value]))],
    summary="执行下发任务（提交 Celery）",
)
async def execute_task(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse] | JSONResponse:
    """执行已审批通过的下发任务。

    该接口会将执行逻辑委托给 Celery 异步队列，避免前端长连接阻塞。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Raises:
        BadRequestException: 如果任务类型不匹配或任务未处于"已审批"状态。

    Returns:
        ResponseBase[DeployTaskResponse]: 已绑定 Celery 任务 ID 的详情。
    """
    task = await service.execute_task(task_id)
    task_response = DeployTaskResponse.model_validate(task)
    if task_response.result and task_response.result.get("otp_required"):
        return build_otp_required_response(
            message=task_response.error_message or "需要重新输入 OTP 验证码",
            details={
                "otp_required": True,
                "otp_required_groups": task_response.result.get("otp_required_groups"),
                "expires_in": task_response.result.get("expires_in"),
                "next_action": task_response.result.get("next_action"),
            },
        )
    return ResponseBase(data=task_response)


@router.post(
    "/{task_id:uuid}/cancel",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_EXECUTE.value]))],
    summary="取消执行中的任务",
)
async def cancel_task(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse]:
    """取消正在执行的下发任务。

    仅当任务处于 RUNNING 状态时可取消。会尝试终止对应的 Celery 任务。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployTaskResponse]: 取消后的任务详情。
    """
    task = await service.cancel_task(task_id)
    task_response = DeployTaskResponse.model_validate(task)
    return ResponseBase(data=task_response, message="任务已取消")


@router.post(
    "/{task_id:uuid}/retry",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_EXECUTE.value]))],
    summary="重试失败的设备",
)
async def retry_failed_devices(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse]:
    """重试部分成功或失败任务中的失败设备。

    仅当任务处于 PARTIAL 或 FAILED 状态时可重试。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployTaskResponse]: 重新执行后的任务详情。
    """
    task = await service.retry_failed_devices(task_id)
    task_response = DeployTaskResponse.model_validate(task)
    return ResponseBase(data=task_response, message="已开始重试失败设备")


@router.post(
    "/{task_id:uuid}/restore",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[
        Depends(deps.get_current_active_superuser),
        Depends(require_permissions([PermissionCode.DEPLOY_RESTORE.value])),
    ],
    summary="恢复已删除下发任务",
)
async def restore_deploy_task(
    task_id: UUID,
    service: DeployServiceDep,
) -> ResponseBase[DeployTaskResponse]:
    """恢复单个已删除的下发任务至正常状态。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployTaskResponse]: 恢复后的任务详情。
    """
    task = await service.restore_task(task_id=task_id)
    return ResponseBase(data=DeployTaskResponse.model_validate(task), message="下发任务恢复成功")


@router.post(
    "/{task_id:uuid}/rollback/preview",
    response_model=ResponseBase[RollbackPreviewResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_ROLLBACK.value]))],
    summary="回滚预检",
)
async def preview_rollback(
    task_id: UUID,
    service: DeployServiceDep,
) -> ResponseBase[RollbackPreviewResponse] | JSONResponse:
    """回滚预检：连接设备比对 MD5，判断哪些设备需要回滚。

    此接口会连接设备获取当前配置，与变更前备份比对 MD5：
    - MD5 不同：需要回滚
    - MD5 相同：可跳过（配置未变化）

    若存在 otp_manual 设备且 OTP 未缓存，会返回 428 状态码，
    提示前端弹窗让用户输入 OTP 验证码后重试。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[RollbackPreviewResponse]: 回滚预检结果。
        JSONResponse (428): 需要输入 OTP 验证码。
    """
    result = await service.preview_rollback(task_id)

    # 检查是否需要 OTP（服务层标记为 PAUSED）
    if result.summary == "需要输入 OTP 验证码":
        # 获取任务的 OTP 详情
        task = await service.get_task(task_id)
        if task.result and isinstance(task.result, dict) and task.result.get("otp_required"):
            return build_otp_required_response(
                message=task.error_message or "回滚预检需要输入 OTP 验证码",
                details={
                    "otp_required": True,
                    "otp_required_groups": task.result.get("otp_required_groups"),
                    "expires_in": task.result.get("expires_in"),
                    "next_action": "cache_otp_and_retry_preview",
                },
            )

    return ResponseBase(data=result)


@router.post(
    "/{task_id:uuid}/rollback",
    response_model=ResponseBase[DeployRollbackResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_ROLLBACK.value]))],
    summary="触发回滚（Celery）",
)
async def rollback_task(
    task_id: UUID,
    service: DeployServiceDep,
) -> ResponseBase[DeployRollbackResponse] | JSONResponse:
    """对发生故障或需要撤回的下发任务进行回滚操作。

    回滚前会自动检测配置是否变化，只对配置实际变化的设备执行回滚。
    仅支持 SUCCESS、PARTIAL 或 ROLLBACK 状态的任务。

    若存在 otp_manual 设备且 OTP 未缓存，会返回 428 状态码，
    提示前端弹窗让用户输入 OTP 验证码后重试。

    Args:
        task_id (UUID): 原下发任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployRollbackResponse]: 包含回滚 Celery 任务 ID 的响应。
        JSONResponse (428): 需要输入 OTP 验证码。
    """
    # 先验证任务状态是否允许回滚（含 OTP 预检）
    task = await service.validate_rollback(task_id)

    # 检查是否需要 OTP
    if task.result and isinstance(task.result, dict) and task.result.get("otp_required"):
        return build_otp_required_response(
            message=task.error_message or "回滚需要输入 OTP 验证码",
            details={
                "otp_required": True,
                "otp_required_groups": task.result.get("otp_required_groups"),
                "expires_in": task.result.get("expires_in"),
                "next_action": task.result.get("next_action"),
            },
        )

    from app.celery.tasks.deploy import rollback_task

    celery_result = cast(Any, rollback_task).delay(task_id=str(task_id))  # type: ignore[attr-defined]
    return ResponseBase(
        data=DeployRollbackResponse(task_id=task_id, celery_task_id=celery_result.id, status=TaskStatus.RUNNING)
    )


@router.delete(
    "/{task_id:uuid}/hard",
    response_model=ResponseBase[dict],
    dependencies=[
        Depends(deps.get_current_active_superuser),
        Depends(require_permissions([PermissionCode.DEPLOY_DELETE.value])),
    ],
    summary="彻底删除下发任务",
)
async def hard_delete_deploy_task(
    task_id: UUID,
    service: DeployServiceDep,
) -> ResponseBase[dict]:
    """彻底删除单个下发任务（物理删除，不可恢复）。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[dict]: 操作结果消息。
    """
    await service.hard_delete_task(task_id=task_id)
    return ResponseBase(data={"message": "下发任务已彻底删除"}, message="下发任务已彻底删除")
