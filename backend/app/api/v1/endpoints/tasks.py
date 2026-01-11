"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: tasks.py
@DateTime: 2026-01-09 12:00:00
@Docs: 任务管理 API (Celery Task Management API).
"""

from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str, _: SuperuserDep) -> TaskResponse:
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

    return response


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


# ==================== 测试任务 ====================


@router.post("/test/ping", response_model=TaskResponse)
async def trigger_ping(_: SuperuserDep) -> TaskResponse:
    """触发 Ping 测试异步任务。

    用于回归测试或验证 Celery 分片和 Worker 是否正常运行。
    仅限超级管理员访问。

    Args:
        _ (User): 超级管理员权限验证。

    Returns:
        TaskResponse: 返回生成的任务 ID，状态为 PENDING。
    """
    from app.celery.tasks.example import ping

    result = ping.delay()  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


@router.post("/test/add", response_model=TaskResponse)
async def trigger_add(_: SuperuserDep, x: int = 1, y: int = 2) -> TaskResponse:
    """触发一个简单的加法异步测试任务。

    仅限超级管理员访问。

    Args:
        _ (User): 超级管理员权限验证。
        x (int): 第一个操作数。
        y (int): 第二个操作数。

    Returns:
        TaskResponse: 生成的任务 ID。
    """
    from app.celery.tasks.example import add

    result = add.delay(x, y)  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


@router.post("/test/long-running", response_model=TaskResponse)
async def trigger_long_running(_: SuperuserDep, duration: int = 10) -> TaskResponse:
    """触发一个耗时模拟任务，用于测试进度反馈和超时处理。

    仅限超级管理员访问。设置较长的 duration 可以测试撤销任务接口。

    Args:
        _ (User): 超级管理员权限验证。
        duration (int): 模拟运行时长（秒），默认 10s，由于是测试任务，限额 300s。

    Returns:
        TaskResponse: 生成的任务 ID。

    Raises:
        HTTPException: 当 duration 超过 300s 时。
    """
    if duration > 300:
        raise HTTPException(status_code=400, detail="测试任务持续时间不能超过 300 秒")

    from app.celery.tasks.example import long_running

    result = long_running.delay(duration)  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


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
