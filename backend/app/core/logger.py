"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: logger.py
@DateTime: 2025-12-30 13:30:00
@Docs: 使用 structlog 和标准日志记录的结​​构化日志记录配置。
       包括文件轮换、压缩和关注点分离。
"""

import gzip
import logging
import os
import shutil
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Any

import structlog

from app.core.config import settings

# 确保日志目录存在

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    扩展 TimedRotatingFileHandler，用于在轮换时压缩日志文件。
    """

    def __init__(
        self,
        filename: str,
        when: str = "h",
        interval: int = 1,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        utc: bool = False,
        atTime: Any | None = None,
        errors: str | None = None,
    ):
        """初始化压缩时间轮换文件处理器。

        Args:
            filename (str): 日志文件名。
            when (str): 轮换时间单位，默认为 "h"（小时）。
            interval (int): 轮换间隔，默认为 1。
            backupCount (int): 保留的备份文件数量，默认为 0。
            encoding (str | None): 文件编码，默认为 None。
            delay (bool): 是否延迟创建文件，默认为 False。
            utc (bool): 是否使用 UTC 时间，默认为 False。
            atTime (Any | None): 轮换时间，默认为 None。
            errors (str | None): 错误处理方式，默认为 None。
        """
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime, errors)  # 类型：忽略

    def doRollover(self) -> None:
        """执行日志文件轮换。

        当日志文件达到轮换条件时，压缩旧文件并创建新文件。

        Returns:
            None: 无返回值。
        """
        super().doRollover()


def namer(name: str) -> str:
    """自定义命名器，用于在轮换文件时添加 .gz 扩展名。

    Args:
        name (str): 原始文件名。

    Returns:
        str: 添加 .gz 扩展名后的文件名。
    """
    return name + ".gz"


def rotator(source: str, dest: str) -> None:
    """自定义轮换器，使用 gzip 压缩文件。

    Args:
        source (str): 源文件路径。
        dest (str): 目标文件路径（压缩后的文件）。

    Returns:
        None: 无返回值。
    """
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


def get_file_handler(name: str, level: int, filename: str) -> TimedRotatingFileHandler:
    """创建配置的 TimedRotatingFileHandler 的帮助程序。

    使用默认的轮换格式：filename.YYYY-MM-DD

    Args:
        name (str): 处理器名称。
        level (int): 日志级别。
        filename (str): 日志文件名。

    Returns:
        TimedRotatingFileHandler: 配置好的文件处理器。
    """

    file_path = os.path.join(LOG_DIR, filename)
    handler = CompressedTimedRotatingFileHandler(
        file_path,
        when="midnight",
        interval=1,
        backupCount=30,  # 保留30天
        encoding="utf-8",
    )
    handler.setLevel(level)

    # 配置压缩
    handler.rotator = rotator  # type: ignore
    handler.namer = namer  # type: ignore

    return handler


def setup_logging() -> None:
    """配置严格 JSON 日志记录，使用 structlog。

    配置包括：
    - 控制台输出（本地环境为彩色文本，其他环境为 JSON）
    - 文件输出（始终为 JSON 格式）
    - 日志轮换和压缩
    - 独立的 API 流量和 Celery 任务日志记录器

    Returns:
        None: 无返回值。
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # 配置 structlog
    # 注意: 我们不在这里添加 Renderer，而是让 stdlib 的 Formatter 来处理渲染
    # 这样可以实现 控制台->彩色文本，文件->JSON 的混合输出
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 标准输出的格式化程序（取决于环境）
    stdout_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        # 这些 processor 在 "Formatter" 阶段运行
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer()
            if settings.ENVIRONMENT == "local"
            else structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    # 文件格式化程序（始终为 JSON，且无颜色代码）
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # 确保 file log 不包含 ANSI 颜色，并支持中文显示
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    # 根记录器

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []  # 清除现有的

    # 1. 标准输出处理程序

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(stdout_formatter)
    root_logger.addHandler(stream_handler)

    # 2.信息文件处理程序（包含INFO+的所有内容）
    # 我们将其重命名为info.log，logs/info.log

    info_handler = get_file_handler("info_handler", logging.INFO, "info.log")
    info_handler.setFormatter(file_formatter)
    root_logger.addHandler(info_handler)

    # 3.错误文件处理程序（包含ERROR+）

    error_handler = get_file_handler("error_handler", logging.ERROR, "error.log")
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # 4.API流量记录器

    # --- 通用辅助函数：设置独立日志记录器 ---
    def _setup_logger(
        name: str,
        level: int,
        filename: str,
        *,
        add_console_in_local: bool = True,
    ) -> logging.Logger:
        """
        设置独立日志记录器的辅助函数。

        Args:
            name: 日志记录器名称
            level: 日志级别
            filename: 日志文件名
            add_console_in_local: 是否在本地环境添加控制台输出

        Returns:
            logging.Logger: 配置好的日志记录器
        """
        new_logger = logging.getLogger(name)
        new_logger.setLevel(level)
        new_logger.propagate = False  # 不传播到 root，避免重复

        handler = get_file_handler(f"{name}_handler", level, filename)
        handler.setFormatter(file_formatter)
        new_logger.addHandler(handler)

        # 本地环境也输出到控制台
        if add_console_in_local and settings.ENVIRONMENT == "local":
            new_logger.addHandler(stream_handler)

        return new_logger

    # 4. API 流量记录器
    _setup_logger("api_traffic", logging.INFO, "api_traffic.log")

    # 5. Celery Worker 日志记录器（不包含命令执行结果，避免日志过大）
    _setup_logger("celery_task", logging.INFO, "celery.log")

    # 6. Celery Details 日志记录器（包含 LLDP 数据、采集结果等详细信息）
    _setup_logger("celery_details", logging.DEBUG, "celery_details.log")

    # 排除 uvicorn、sqlalchemy 的日志

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = structlog.get_logger()
# 公开访问日志的特定记录器

access_logger = structlog.get_logger("api_traffic")

# Celery 任务日志记录器
celery_task_logger = structlog.get_logger("celery_task")

# Celery 详细日志记录器（用于记录任务执行的详细信息，如 LLDP 数据、采集结果等）
celery_details_logger = structlog.get_logger("celery_details")
