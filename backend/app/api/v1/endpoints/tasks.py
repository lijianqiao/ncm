"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: tasks.py
@DateTime: 2026-01-09 12:00:00
@Docs: 任务管理 API (Celery Task Management API).
"""

from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_superuser
from app.celery.app import celery_app
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter()

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


# ==================== 任务查询 ====================


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


class RevokeResponse(BaseModel):
    """任务撤销响应。"""

    message: str = Field(..., description="操作结果消息")


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


# ==================== Worker 状态 ====================


class WorkerStatsResponse(BaseModel):
    """Worker 统计响应。"""

    workers: list[str] = Field(default_factory=list, description="Worker 列表")
    active_tasks: dict[str, int] = Field(default_factory=dict, description="各 Worker 活跃任务数")
    stats: dict[str, Any] = Field(default_factory=dict, description="详细统计信息")


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
