"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: event_bus.py
@DateTime: 2025-12-30 15:25:00
@Docs: 轻量级事件总线 (Simple Event Bus for Decoupling).
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from app.core.logger import logger


@dataclass
class Event:
    """
    事件基类。所有自定义事件应继承此类。
    """

    pass


@dataclass
class OperationLogEvent(Event):
    """
    操作日志事件。
    """

    user_id: str
    username: str
    ip: str | None
    method: str
    path: str
    status_code: int
    process_time: float
    params: Any | None = None
    response_result: Any | None = None
    user_agent: str | None = None


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    简单的内存事件总线。

    支持:
    - subscribe(event_type, handler): 订阅事件。
    - publish(event): 发布事件，异步执行所有订阅者。
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)
        self._pending_tasks: set[asyncio.Task] = set()

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        """
        订阅指定类型的事件。
        """
        self._handlers[event_type].append(handler)
        logger.info(f"已订阅事件: {event_type.__name__} -> {handler.__name__}")

    async def publish(self, event: Event) -> None:
        """
        发布事件。所有订阅者将异步执行。
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug(f"未找到事件订阅者: {event_type.__name__}")
            return

        # 创建所有 handler 的任务（不阻塞主流程，但会跟踪任务，便于 shutdown 时 drain）
        tasks = [asyncio.create_task(self._safe_call(handler, event)) for handler in handlers]
        for task in tasks:
            self._pending_tasks.add(task)
            task.add_done_callback(lambda t: self._pending_tasks.discard(t))

        logger.debug(f"已发布事件: {event_type.__name__} -> {len(tasks)} 订阅者")

    async def drain(self, timeout: float = 5.0) -> None:
        """尽量等待已发布但未完成的事件处理任务完成。

        说明：这是“尽力而为”的可靠性增强，不保证强一致。
        """

        if not self._pending_tasks:
            return

        tasks = list(self._pending_tasks)
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except TimeoutError:
            logger.warning(f"事件总线 drain 超时，剩余任务数: {len(self._pending_tasks)}")

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """
        安全调用 handler，捕获异常防止影响其他 handler。
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"事件处理错误 ({handler.__name__}): {e}")


# 全局事件总线实例
event_bus = EventBus()
