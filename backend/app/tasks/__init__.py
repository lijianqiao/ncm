"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 11:50:00
@Docs: Celery 任务模块入口 (Celery Tasks Module).
"""

from app.tasks.base import BaseTask

__all__ = ["BaseTask"]
