"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-01-09 13:00:00
@Docs: Celery 任务集合 (Celery Tasks Collection).
"""

# 导入所有任务模块以确保任务被注册
from app.celery.tasks import backup, example

__all__ = ["backup", "example"]
