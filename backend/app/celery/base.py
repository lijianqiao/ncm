"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: base.py
@DateTime: 2026-01-09 11:50:00
@Docs: Celery 基础任务类 (Base Celery Task).
"""

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, TypeVar

from celery import Task

from app.core.logger import logger

T = TypeVar("T")

# 默认 run_async 超时时间（秒），避免无限等待
DEFAULT_RUN_ASYNC_TIMEOUT = 3600  # 1 小时

_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_THREAD: threading.Thread | None = None
_ASYNC_THREAD_STARTED = threading.Event()
_ASYNC_LOCK = threading.Lock()


def init_celery_async_runtime() -> None:
    """初始化 Celery Worker 进程的异步运行时（后台事件循环线程）。

    目标：
    - Celery 在 Windows 或 threads pool 下可能在不同线程中执行任务。
    - 直接在调用线程创建/复用事件循环容易导致 asyncpg 的连接 Future 绑定到不同 loop。
    - 这里用“单后台线程 + 单事件循环”，所有协程都提交到该 loop 执行。
    """

    global _ASYNC_LOOP, _ASYNC_THREAD

    with _ASYNC_LOCK:
        if _ASYNC_THREAD and _ASYNC_THREAD.is_alive() and _ASYNC_LOOP and not _ASYNC_LOOP.is_closed():
            return

        _ASYNC_THREAD_STARTED.clear()

        def _thread_main() -> None:
            global _ASYNC_LOOP
            # Python 3.10+ 在 Windows 上默认使用 ProactorEventLoop，无需手动指定
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _ASYNC_LOOP = loop
            _ASYNC_THREAD_STARTED.set()
            loop.run_forever()

            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()

        _ASYNC_THREAD = threading.Thread(target=_thread_main, name="celery-async-runtime", daemon=True)
        _ASYNC_THREAD.start()

    _ASYNC_THREAD_STARTED.wait(timeout=10)


def close_celery_async_runtime() -> None:
    """关闭 Celery Worker 进程异步运行时。"""

    global _ASYNC_LOOP, _ASYNC_THREAD

    with _ASYNC_LOCK:
        loop = _ASYNC_LOOP
        thread = _ASYNC_THREAD
        _ASYNC_LOOP = None
        _ASYNC_THREAD = None

    if loop and not loop.is_closed():
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
    if thread and thread.is_alive():
        thread.join(timeout=5)


def run_async[T](coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """在同步 Celery 任务中运行异步代码。

    智能检测当前是否已有事件循环运行：
    - 无运行中的事件循环：直接使用 asyncio.run()
    - 已有事件循环运行：在线程池中执行，避免嵌套循环

    Args:
        coro: 要执行的异步协程
        timeout: 超时时间（秒），默认为 DEFAULT_RUN_ASYNC_TIMEOUT (1 小时)

    Returns:
        协程的返回值

    Raises:
        TimeoutError: 协程执行超时
        RuntimeError: 事件循环状态异常

    Example:
        @celery_app.task(base=BaseTask)
        def my_task():
            async def _async_work():
                async with AsyncSessionLocal() as db:
                    return await some_service.do_something(db)
            return run_async(_async_work())
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("禁止在运行中的事件循环中调用 run_async()")

    init_celery_async_runtime()
    loop = _ASYNC_LOOP
    thread = _ASYNC_THREAD
    if not loop or loop.is_closed() or not thread or not thread.is_alive():
        raise RuntimeError("Celery 异步运行时未初始化")
    if threading.get_ident() == thread.ident:
        raise RuntimeError("禁止在 Celery 异步运行时线程内调用 run_async()")

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    effective_timeout = timeout if timeout is not None else DEFAULT_RUN_ASYNC_TIMEOUT
    try:
        return future.result(timeout=effective_timeout)
    except FutureTimeoutError as e:
        future.cancel()
        raise TimeoutError(f"run_async 超时 ({effective_timeout}s)") from e


def safe_update_state(
    task: Task,
    celery_task_id: str | None,
    *,
    state: str,
    meta: dict[str, Any] | None = None,
    **kwargs: Any,
) -> bool:
    """
    安全更新工具

    Args:
        task: Celery 任务实例
        celery_task_id: Celery 任务 ID
        state: 任务状态
        meta: 任务元数据
        kwargs: 其他参数

    Returns:
        是否更新成功

    """
    if not celery_task_id:
        return False
    try:
        task.update_state(task_id=celery_task_id, state=state, meta=meta, **kwargs)
        return True
    except Exception as e:
        logger.warning(
            "更新任务状态失败",
            task_id=celery_task_id,
            task_name=getattr(task, "name", None),
            error=str(e),
            exc_info=True,
        )
        return False


class BaseTask(Task):
    """
    NCM 系统的 Celery 基础任务类。

    提供：
    - 统一的日志记录
    - 任务执行前后的钩子
    - 错误处理与重试逻辑

    所有 NCM 任务应继承此类以获得统一的行为。

    注意：
    - autoretry_for 仅针对可恢复的临时性错误（网络超时、连接错误等）
    - 业务逻辑错误（如参数校验失败）不应自动重试
    - 高危操作（如下发任务）应单独设置 autoretry_for=() 禁用自动重试
    """

    # 默认重试配置：仅针对可恢复的临时性错误
    # 注意：不要使用 (Exception,)，这会导致所有异常都被重试
    autoretry_for = (
        ConnectionError,  # 网络连接错误
        TimeoutError,  # 超时错误
        OSError,  # 系统级 I/O 错误（包含网络相关）
    )
    retry_backoff = True  # 指数退避
    retry_backoff_max = 600  # 最大退避时间 10 分钟
    retry_jitter = True  # 添加随机抖动
    max_retries = 3  # 最大重试次数

    # Celery 官方推荐：acks_late + reject_on_worker_lost 组合使用
    # 确保 Worker 崩溃/被终止时任务会重新入队而不是丢失
    acks_late = True
    reject_on_worker_lost = True

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
