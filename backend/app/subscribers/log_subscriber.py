"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log_subscriber.py
@DateTime: 2025-12-30 15:30:00
@Docs: 日志事件订阅者 (Log Event Subscriber).
"""

import uuid

from app.core.db import AsyncSessionLocal
from app.core.event_bus import Event, OperationLogEvent, event_bus
from app.core.logger import logger
from app.models.log import OperationLog


async def handle_operation_log_event(event: Event) -> None:
    """处理操作日志事件，写入数据库。

    Args:
        event: 事件对象，需为 OperationLogEvent 类型

    Raises:
        Exception: 数据库操作异常（已记录日志）
    """
    if not isinstance(event, OperationLogEvent):
        return

    async with AsyncSessionLocal() as session:
        try:
            # 简单的模块名提取 (例如 /api/v1/users/ -> users)
            parts = event.path.strip("/").split("/")
            module = "unknown"
            if len(parts) >= 3 and parts[0] == "api":
                module = parts[2]

            summary = f"{event.method} {event.path}"

            user_id: uuid.UUID | None
            try:
                user_id = uuid.UUID(event.user_id)
            except Exception:
                user_id = None

            log = OperationLog(
                user_id=user_id,
                username=event.username,
                ip=event.ip,
                module=module,
                summary=summary,
                method=event.method,
                path=event.path,
                params=event.params,
                response_code=event.status_code,
                response_result=event.response_result,
                duration=event.process_time,
                user_agent=event.user_agent,
            )
            session.add(log)
            await session.commit()
            logger.debug(f"操作日志已保存: {summary}")
        except Exception as e:
            logger.error(f"保存操作日志失败: {e}")


def register_log_subscribers() -> None:
    """
    注册日志相关的事件订阅者。应在应用启动时调用。

    将 handle_operation_log_event 注册为 OperationLogEvent 的订阅者。
    """
    event_bus.subscribe(OperationLogEvent, handle_operation_log_event)
