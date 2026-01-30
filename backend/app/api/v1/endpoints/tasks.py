"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: tasks.py
@DateTime: 2026-01-09 12:00:00
@Docs: 任务管理 API (Celery Task Management API).

路由顺序规则：
    1. 根路由 `/` - 最先定义
    2. 静态路由 - 固定路径如 `/workers/stats`
    3. 动态路由 - 带路径参数如 `/{task_id}` 及其子路由

    原因：FastAPI 按定义顺序匹配路由，静态路由必须在动态路由之前，
    否则 `/workers/stats` 会被 `/{task_id}` 错误捕获（task_id="workers"）。
"""

from typing import Annotated, Any
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    BackupServiceDep,
    DeployServiceDep,
    get_current_active_superuser,
)
from app.celery.app import celery_app
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.otp import otp_coordinator
from app.models.user import User
from app.schemas.backup import BackupBatchRequest
from app.schemas.common import ResponseBase
from app.core.enums import BackupType

router = APIRouter(tags=["任务管理"])

# 超级管理员依赖注解
SuperuserDep = Annotated[User, Depends(get_current_active_superuser)]


class TaskResponse(BaseModel):
    """任务响应模型。"""

    task_id: str
    status: str
    result: Any | None = None
    error: str | None = None


class TaskTriggerRequest(BaseModel):
    """任务触发请求模型。"""

    task_name: str
    args: list[Any] = []
    kwargs: dict[str, Any] = {}


class RevokeResponse(BaseModel):
    """任务撤销响应。"""

    message: str = Field(..., description="操作结果消息")


class WorkerStatsResponse(BaseModel):
    """Worker 统计响应。"""

    workers: list[str] = Field(default_factory=list, description="Worker 列表")
    active_tasks: dict[str, int] = Field(default_factory=dict, description="各 Worker 活跃任务数")
    stats: dict[str, Any] = Field(default_factory=dict, description="详细统计信息")


# ==================== 静态路由 (Static Routes) ====================


@router.get("/workers/stats", response_model=ResponseBase[WorkerStatsResponse])
async def get_worker_stats(_: SuperuserDep) -> ResponseBase[WorkerStatsResponse]:
    """实时获取当前已注册的所有 Celery Worker 节点的统计状态。

    仅限超级管理员访问。返回包括并发设置、已完成任务数、运行中的任务等。

    Args:
        _ (User): 超级管理员权限验证。

    Returns:
        ResponseBase[WorkerStatsResponse]: 包含 workers 列表、stats 统计和活动任务详情。
    """
    inspect = celery_app.control.inspect()

    # 获取活跃的 Workers
    active_workers = inspect.active() or {}
    stats = inspect.stats() or {}

    return ResponseBase(
        data=WorkerStatsResponse(
            workers=list(active_workers.keys()),
            active_tasks={worker: len(tasks) for worker, tasks in active_workers.items()},
            stats=stats,
        )
    )


# ==================== 动态路由 (Dynamic Routes) ====================


@router.get("/{task_id}", response_model=ResponseBase[TaskResponse])
async def get_task_status(task_id: str, _: SuperuserDep) -> ResponseBase[TaskResponse]:
    """查询 Celery 任务的执行状态和结果。

    仅限超级管理员访问。能够返回 PENDING, STARTED, SUCCESS, FAILURE 等状态，并在任务完成时返回结果或错误。

    Args:
        task_id (str): Celery 任务的唯一 ID。
        _ (User): 超级管理员权限验证。

    Returns:
        TaskResponse: 包含任务 ID、状态、以及（如有）执行结果或错误的对象。
    """
    result = AsyncResult(task_id, app=celery_app)

    response = TaskResponse(
        task_id=task_id,
        status=result.status,
    )

    if result.successful():
        response.result = result.result
    elif result.failed():
        response.error = str(result.result)
    elif result.status == "PROGRESS":
        # 进度信息
        response.result = result.info

    return ResponseBase(data=response)


@router.delete("/{task_id}", response_model=ResponseBase[RevokeResponse])
async def revoke_task(task_id: str, _: SuperuserDep) -> ResponseBase[RevokeResponse]:
    """撤销或强制终止正在执行的任务。

    仅限超级管理员访问。

    Args:
        task_id (str): 要撤销的任务 ID。
        _ (User): 超级管理员权限验证。

    Returns:
        ResponseBase[RevokeResponse]: 操作确认信息。
    """
    celery_app.control.revoke(task_id, terminate=True)
    return ResponseBase(data=RevokeResponse(message=f"任务 {task_id} 已被撤销"))


@router.post("/{task_id}/resume", response_model=ResponseBase[dict])
async def resume_task_group(
    task_id: str,
    backup_service: BackupServiceDep,
    deploy_service: DeployServiceDep,
    _: SuperuserDep,
    dept_id: UUID = Query(..., description="部门ID"),
    group: str = Query(..., description="设备分组"),
) -> ResponseBase[dict]:
    """恢复指定任务中某个分组的执行。

    Args:
        task_id: 任务 ID。
        backup_service: 备份服务依赖。
        deploy_service: 下发服务依赖。
        _: 超级管理员权限依赖。
        dept_id: 部门 ID。
        group: 设备分组。

    Returns:
        ResponseBase[dict]: 恢复结果与任务 ID 信息。

    Raises:
        NotFoundException: 任务不存在或不支持恢复。
        BadRequestException: 找不到可恢复的设备或任务类型不支持。
    """
    batch_info = await otp_coordinator.registry.get_batch(task_id)
    if not batch_info:
        raise NotFoundException(message="任务不存在或不支持恢复")

    pause_state = await otp_coordinator.resume_group(task_id, dept_id, group)
    pending_ids = [UUID(str(x)) for x in (pause_state.get("pending_device_ids") if pause_state else []) or []]
    task_type = batch_info.get("task_type")
    if not pending_ids and task_type == "deploy":
        pending_ids = await deploy_service.get_group_device_ids(UUID(task_id), dept_id, group)
    if not pending_ids:
        raise BadRequestException(message="未找到可恢复的设备")
    if task_type == "backup":
        backup_type = batch_info.get("backup_type") or "manual"
        operator_id = batch_info.get("operator_id")
        request = BackupBatchRequest(
            device_ids=pending_ids,
            backup_type=BackupType(backup_type),
            resume_task_id=task_id,
        )
        result = await backup_service.backup_devices_batch(
            request,
            operator_id=UUID(str(operator_id)) if operator_id else None,
        )
        return ResponseBase(data={"task_id": task_id, "resume_task_id": result.task_id})

    if task_type == "deploy":
        result = await deploy_service.resume_task_by_device_ids(UUID(task_id), pending_ids)
        return ResponseBase(data={"task_id": str(result.id), "celery_task_id": result.celery_task_id})

    raise BadRequestException(message="当前任务类型不支持恢复")
