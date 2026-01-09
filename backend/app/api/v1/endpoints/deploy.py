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

from app.api.deps import CurrentUser, DeployServiceDep, require_permissions
from app.core.enums import TaskStatus, TaskType
from app.core.exceptions import BadRequestException
from app.core.permissions import PermissionCode
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.deploy import (
    DeployApproveRequest,
    DeployCreateRequest,
    DeployRollbackResponse,
    DeployTaskResponse,
)

router = APIRouter(prefix="/deploy", tags=["安全批量下发"])


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
async def execute_task(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse]:
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
    task = await service.get_task(task_id)
    if task.task_type != TaskType.DEPLOY.value:
        raise BadRequestException("仅支持下发任务")
    if task.status != TaskStatus.APPROVED.value:
        raise BadRequestException("任务未审批通过")

    from app.celery.tasks.deploy import deploy_task

    celery_result = cast(Any, deploy_task).delay(task_id=str(task_id))  # type: ignore[attr-defined]
    task = await service.bind_celery_task(task_id, celery_task_id=celery_result.id)
    return ResponseBase(data=DeployTaskResponse.model_validate(task))


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
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseBase[PaginatedResponse[DeployTaskResponse]]:
    """获取所有批量配置下发任务的列表。

    Args:
        service (DeployService): 下发服务依赖。
        page (int): 当前页码。
        page_size (int): 每页限制数量。

    Returns:
        ResponseBase[PaginatedResponse[DeployTaskResponse]]: 分页后的任务概览。
    """
    # 临时：复用 CRUD 的分页过滤能力
    items, total = await service.task_crud.get_multi_paginated_filtered(
        service.db,
        page=page,
        page_size=page_size,
        task_type=TaskType.DEPLOY.value,
    )
    return ResponseBase(
        data=PaginatedResponse(
            items=[DeployTaskResponse.model_validate(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{task_id}",
    response_model=ResponseBase[DeployTaskResponse],
    dependencies=[Depends(require_permissions([PermissionCode.DEPLOY_VIEW.value]))],
    summary="下发任务详情",
)
async def get_deploy_task(task_id: UUID, service: DeployServiceDep) -> ResponseBase[DeployTaskResponse]:
    """获取下发任务的完整详细信息。

    Args:
        task_id (UUID): 任务 ID。
        service (DeployService): 下发服务依赖。

    Returns:
        ResponseBase[DeployTaskResponse]: 包含设备下发日志及状态的详细数据。
    """
    task = await service.get_task(task_id)
    return ResponseBase(data=DeployTaskResponse.model_validate(task))
