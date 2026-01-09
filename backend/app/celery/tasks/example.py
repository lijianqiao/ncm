"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: example.py
@DateTime: 2026-01-09 11:50:00
@Docs: 示例任务 (Example Tasks for Testing).
"""

import time

from app.celery.app import celery_app
from app.celery.base import BaseTask
from app.core.logger import logger


@celery_app.task(base=BaseTask, bind=True, name="app.celery.tasks.example.ping")
def ping(self) -> dict:
    """
    简单的 Ping 任务，用于验证 Celery 连接。

    Returns:
        dict: 包含状态和消息的字典。
    """
    logger.info("Ping 任务被调用", task_id=self.request.id)
    return {"status": "pong", "message": "Celery 连接正常"}


@celery_app.task(base=BaseTask, bind=True, name="app.celery.tasks.example.add")
def add(self, x: int, y: int) -> int:
    """
    简单的加法任务，用于测试参数传递。

    Args:
        x: 第一个加数
        y: 第二个加数

    Returns:
        int: 两数之和
    """
    result = x + y
    logger.info("加法任务完成", task_id=self.request.id, x=x, y=y, result=result)
    return result


@celery_app.task(base=BaseTask, bind=True, name="app.celery.tasks.example.long_running")
def long_running(self, duration: int = 10) -> dict:
    """
    长时间运行的任务，用于测试任务状态追踪。

    Args:
        duration: 任务持续时间（秒）

    Returns:
        dict: 包含执行信息的字典
    """
    logger.info("长时间任务开始", task_id=self.request.id, duration=duration)

    for i in range(duration):
        # 更新任务进度状态
        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": duration, "percent": (i + 1) / duration * 100},
        )
        time.sleep(1)

    logger.info("长时间任务完成", task_id=self.request.id)
    return {"status": "completed", "duration": duration}
