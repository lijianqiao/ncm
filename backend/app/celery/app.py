"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: app.py
@DateTime: 2026-01-09 11:45:00
@Docs: Celery 应用配置 (Celery Application Configuration).
"""

import multiprocessing
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init, worker_process_init, worker_shutdown

from app.core.config import settings


@worker_init.connect
def _init_worker_redis(**_kwargs) -> None:
    """初始化 Worker 需要的外部资源（如 Redis）。"""
    from app.core.logger import logger

    # Linux prefork(fork) 场景下，worker_init 发生在主进程，事件循环不应在 fork 前初始化。
    if os.name != "nt":
        try:
            start_method = multiprocessing.get_start_method(allow_none=True)
        except Exception:
            start_method = None
        if start_method == "fork":
            return

    try:
        from app.celery.base import init_celery_async_runtime, run_async
        from app.core.cache import init_redis

        init_celery_async_runtime()
        run_async(init_redis())
    except Exception as e:
        # 初始化失败不阻断 worker 启动（任务会降级运行），但记录警告日志
        logger.warning("Worker 初始化 Redis 失败，任务将降级运行", error=str(e), exc_info=True)


@worker_process_init.connect
def _init_worker_process_redis(**_kwargs) -> None:
    """prefork 模式下的子进程初始化。"""
    from app.core.logger import logger

    try:
        from app.celery.base import init_celery_async_runtime, run_async
        from app.core.cache import init_redis

        init_celery_async_runtime()
        run_async(init_redis())
    except Exception as e:
        # 初始化失败不阻断子进程启动，但记录警告日志
        logger.warning("Worker 子进程初始化 Redis 失败", error=str(e), exc_info=True)


@worker_shutdown.connect
def _close_worker_redis(**_kwargs) -> None:
    """Worker 关闭时清理资源。"""
    from app.core.logger import logger

    try:
        from app.celery.base import close_celery_async_runtime, run_async
        from app.core.cache import close_redis

        run_async(close_redis())
        close_celery_async_runtime()
    except Exception as e:
        # 关闭失败不影响退出，但记录警告日志
        logger.warning("Worker 关闭时清理资源失败", error=str(e), exc_info=True)


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
            "app.celery.tasks.deploy.*": {"queue": "deploy"},
            # collect 任务（ARP/MAC 采集）与 discovery 任务性质相似，复用 discovery 队列
            "app.celery.tasks.collect.*": {"queue": "discovery"},
            "app.celery.tasks.inventory_audit.*": {"queue": "discovery"},
            "app.celery.tasks.discovery.*": {"queue": "discovery"},
            "app.celery.tasks.alerts.*": {"queue": "discovery"},
            "app.celery.tasks.topology.*": {"queue": "topology"},
        },
        # 定时任务调度 (Celery Beat)
        beat_schedule={
            # 每日定时全量配置备份
            "daily-backup-all": {
                "task": "app.celery.tasks.backup.scheduled_backup_all",
                "schedule": crontab(
                    hour=str(settings.CELERY_BEAT_BACKUP_HOUR),
                    minute=str(settings.CELERY_BEAT_BACKUP_MINUTE),
                ),
                "options": {"queue": "backup"},
            },
            # 定时增量配置检查（检测配置变更）
            "incremental-backup-check": {
                "task": "app.celery.tasks.backup.incremental_backup_check",
                "schedule": crontab(
                    minute="0",
                    hour=settings.CELERY_BEAT_INCREMENTAL_HOURS,
                ),
                "options": {"queue": "backup"},
            },
            # 定时 ARP/MAC 表采集
            "hourly-collect-all": {
                "task": "app.celery.tasks.collect.scheduled_collect_all",
                "schedule": crontab(minute=str(settings.CELERY_BEAT_COLLECT_MINUTE)),
                "options": {"queue": "discovery"},
            },
            # 定时网络扫描
            "daily-network-scan": {
                "task": "app.celery.tasks.discovery.scheduled_network_scan",
                "schedule": crontab(
                    hour=str(settings.CELERY_BEAT_SCAN_HOUR),
                    minute=str(settings.CELERY_BEAT_SCAN_MINUTE),
                ),
                "options": {"queue": "discovery"},
            },
            # 定时离线天数更新
            "daily-offline-increment": {
                "task": "app.celery.tasks.discovery.increment_offline_days",
                "schedule": crontab(hour="0", minute="30"),  # 每日 00:30
                "options": {"queue": "discovery"},
            },
            # 定时拓扑刷新
            "daily-topology-refresh": {
                "task": "app.celery.tasks.topology.scheduled_topology_refresh",
                "schedule": crontab(hour=str(settings.CELERY_BEAT_TOPOLOGY_HOUR), minute="0"),
                "options": {"queue": "topology"},
            },
            # 定时告警扫描（离线/影子资产）
            "daily-alert-scan": {
                "task": "app.celery.tasks.alerts.scheduled_offline_alerts",
                "schedule": crontab(hour="1", minute="0"),
                "options": {"queue": "discovery"},
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
