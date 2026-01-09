"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2026-01-09 11:50:00
@Docs: Celery 基础任务类 (Base Celery Task).
"""

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery import Task

from app.core.logger import logger

T = TypeVar("T")


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """在同步 Celery 任务中运行异步代码。

    智能检测当前是否已有事件循环运行：
    - 无运行中的事件循环：直接使用 asyncio.run()
    - 已有事件循环运行：在线程池中执行，避免嵌套循环

    Args:
        coro: 要执行的异步协程

    Returns:
        协程的返回值

    Example:
        @celery_app.task(base=BaseTask)
        def my_task():
            async def _async_work():
                async with AsyncSessionLocal() as db:
                    return await some_service.do_something(db)
            return run_async(_async_work())
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有事件循环运行，在线程池中执行
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


class BaseTask(Task):
    """
    NCM 系统的 Celery 基础任务类。

    提供：
    - 统一的日志记录
    - 任务执行前后的钩子
    - 错误处理与重试逻辑

    所有 NCM 任务应继承此类以获得统一的行为。
    """

    # 默认重试配置
    autoretry_for = (Exception,)
    retry_backoff = True  # 指数退避
    retry_backoff_max = 600  # 最大退避时间 10 分钟
    retry_jitter = True  # 添加随机抖动
    max_retries = 3  # 最大重试次数

    def on_success(self, retval, task_id: str, args, kwargs) -> None:
        """任务成功完成时的回调。"""
        logger.info(
            "任务执行成功",
            task_id=task_id,
            task_name=self.name,
            result_type=type(retval).__name__,
        )

    def on_failure(self, exc, task_id: str, args, kwargs, einfo) -> None:
        """任务失败时的回调。"""
        logger.error(
            "任务执行失败",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            exc_info=True,
        )

    def on_retry(self, exc, task_id: str, args, kwargs, einfo) -> None:
        """任务重试时的回调。"""
        logger.warning(
            "任务重试中",
            task_id=task_id,
            task_name=self.name,
            retry_count=self.request.retries,
            error=str(exc),
        )

    def before_start(self, task_id: str, args, kwargs) -> None:
        """任务开始前的回调。"""
        logger.info(
            "任务开始执行",
            task_id=task_id,
            task_name=self.name,
        )
