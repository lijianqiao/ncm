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
from pydantic import BaseModel

from app.api.deps import get_current_active_superuser
from app.celery.app import celery_app
from app.models.user import User

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
    """
    查询任务执行状态。

    仅限超级管理员访问。
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


@router.delete("/{task_id}")
async def revoke_task(task_id: str, _: SuperuserDep) -> dict:
    """
    撤销/终止正在执行的任务。

    仅限超级管理员访问。
    """
    celery_app.control.revoke(task_id, terminate=True)
    return {"message": f"任务 {task_id} 已被撤销"}


# ==================== 测试任务 ====================


@router.post("/test/ping", response_model=TaskResponse)
async def trigger_ping(_: SuperuserDep) -> TaskResponse:
    """
    触发 Ping 测试任务。

    用于验证 Celery Worker 是否正常运行。
    仅限超级管理员访问。
    """
    from app.celery.tasks.example import ping

    result = ping.delay()  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


@router.post("/test/add", response_model=TaskResponse)
async def trigger_add(_: SuperuserDep, x: int = 1, y: int = 2) -> TaskResponse:
    """
    触发加法测试任务。

    仅限超级管理员访问。
    """
    from app.celery.tasks.example import add

    result = add.delay(x, y)  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


@router.post("/test/long-running", response_model=TaskResponse)
async def trigger_long_running(_: SuperuserDep, duration: int = 10) -> TaskResponse:
    """
    触发长时间运行测试任务。

    仅限超级管理员访问。

    Args:
        duration: 任务持续时间（秒），默认 10 秒
    """
    if duration > 300:
        raise HTTPException(status_code=400, detail="测试任务持续时间不能超过 300 秒")

    from app.celery.tasks.example import long_running

    result = long_running.delay(duration)  # type: ignore[attr-defined]
    return TaskResponse(task_id=result.id, status="PENDING")


# ==================== Worker 状态 ====================


@router.get("/workers/stats")
async def get_worker_stats(_: SuperuserDep) -> dict:
    """
    获取 Celery Worker 状态统计。

    仅限超级管理员访问。
    """
    inspect = celery_app.control.inspect()

    # 获取活跃的 Workers
    active_workers = inspect.active() or {}
    stats = inspect.stats() or {}

    return {
        "workers": list(active_workers.keys()),
        "active_tasks": {worker: len(tasks) for worker, tasks in active_workers.items()},
        "stats": stats,
    }
