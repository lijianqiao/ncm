"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: app.py
@DateTime: 2026-01-09 11:45:00
@Docs: Celery 应用配置 (Celery Application Configuration).
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


def create_celery_app() -> Celery:
    """
    创建并配置 Celery 应用实例。

    Returns:
        Celery: 配置完成的 Celery 应用实例。
    """
    celery_app = Celery(
        "ncm_worker",
        broker=str(settings.CELERY_BROKER_URL),
        backend=str(settings.CELERY_RESULT_BACKEND),
    )

    # Celery 配置
    celery_app.conf.update(
        # 任务序列化
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        # 时区
        timezone="Asia/Shanghai",
        enable_utc=True,
        # 任务配置
        task_track_started=True,
        task_time_limit=3600,  # 单个任务最大执行时间 1 小时
        task_soft_time_limit=3300,  # 软超时 55 分钟，允许任务优雅退出
        # 结果配置
        result_expires=86400,  # 结果保留 24 小时
        result_extended=True,  # 保存更详细的结果信息
        # Worker 配置
        worker_prefetch_multiplier=1,  # 每次只预取 1 个任务，适合长时间任务
        worker_concurrency=4,  # 默认并发数，可通过启动参数覆盖
        # 任务路由
        task_routes={
            "app.celery.tasks.backup.*": {"queue": "backup"},
            "app.celery.tasks.discovery.*": {"queue": "discovery"},
            "app.celery.tasks.topology.*": {"queue": "topology"},
        },
        # 定时任务调度 (Celery Beat)
        beat_schedule={
            # 每日定时全量配置备份
            "daily-backup-all": {
                "task": "app.celery.tasks.backup.scheduled_backup_all",
                "schedule": crontab(
                    hour=settings.CELERY_BEAT_BACKUP_HOUR,
                    minute=settings.CELERY_BEAT_BACKUP_MINUTE,
                ),
                "options": {"queue": "backup"},
            },
            # 定时增量配置检查（检测配置变更）
            "incremental-backup-check": {
                "task": "app.celery.tasks.backup.incremental_backup_check",
                "schedule": crontab(
                    minute=0,
                    hour=settings.CELERY_BEAT_INCREMENTAL_HOURS,
                ),
                "options": {"queue": "backup"},
            },
        },
        # Beat 调度器配置
        beat_scheduler="celery.beat:PersistentScheduler",
        beat_schedule_filename="celerybeat-schedule",
    )

    # 自动发现任务模块
    celery_app.autodiscover_tasks(["app.celery.tasks"])

    return celery_app


# 创建全局 Celery 应用实例
celery_app = create_celery_app()
