"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 12:55:00
@Docs: Celery 任务模块 (Celery Tasks Module).

包含 Celery 应用配置、基础任务类和各类异步任务。
"""

from app.celery.app import celery_app
from app.celery.base import BaseTask

__all__ = ["celery_app", "BaseTask"]
