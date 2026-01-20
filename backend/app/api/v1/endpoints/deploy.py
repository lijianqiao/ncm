"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy.py
@DateTime: 2026-01-09 23:45:00
@Docs: 安全批量下发 API。
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
)

router = APIRouter(tags=["安全批量下发"])


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


@router.post(
    "/{task_id}/approve",
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

    支持多级审批逻辑。如果所有级别均已通过，任务状态将更新为“已审批”。

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
    "/{task_id}/execute",
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
        BadRequestException: 如果任务类型不匹配或任务未处于“已审批”状态。

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
    "/{task_id}/rollback",
    response_model=ResponseBase[DeployRollbackResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_ROLLBACK.value]))],
    summary="触发回滚（Celery）",
)
async def rollback_task(task_id: UUID) -> ResponseBase[DeployRollbackResponse]:
    """对发生故障或需要撤回的下发任务进行回滚操作。

    回滚通常通过在设备上执行反向指令或还原历史配置实现（具体视设备支持而定）。

    Args:
        task_id (UUID): 原下发任务 ID。

    Returns:
        ResponseBase[DeployRollbackResponse]: 包含回滚 Celery 任务 ID 的响应。
    """
    from app.celery.tasks.deploy import rollback_task

    celery_result = cast(Any, rollback_task).delay(task_id=str(task_id))  # type: ignore[attr-defined]
    return ResponseBase(
        data=DeployRollbackResponse(task_id=task_id, celery_task_id=celery_result.id, status=TaskStatus.RUNNING)
    )


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
    success_count, failed_ids = await service.batch_delete_tasks(ids=request.ids, hard_delete=request.hard_delete)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功删除 {success_count} 个下发任务" if not failed_ids else "部分删除成功",
        )
    )


@router.delete(
    "/{task_id}",
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
    success_count, failed_ids = await service.batch_restore_tasks(ids=request.ids)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功恢复 {success_count} 个下发任务" if not failed_ids else "部分恢复成功",
        )
    )


@router.post(
    "/{task_id}/restore",
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


@router.delete(
    "/{task_id}/hard",
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
    success_count, failed_ids = await service.batch_delete_tasks(ids=request.ids, hard_delete=True)
    return ResponseBase(
        data=BatchOperationResult(
            success_count=success_count,
            failed_ids=failed_ids,
            message=f"成功彻底删除 {success_count} 个下发任务" if not failed_ids else "部分彻底删除成功",
        )
    )


@router.get(
    "/{task_id}",
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
