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
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime, errors)  # 类型：忽略

    def doRollover(self) -> None:
        """
        执行轮换，如 __init__() 中所述。
        """
        super().doRollover()


def namer(name: str) -> str:
    """
    自定义命名器，用于在轮换文件时添加 .gz 扩展名。
    """
    return name + ".gz"


def rotator(source: str, dest: str) -> None:
    """
    Custom rotator to compress the file using gzip.
    """
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


def get_file_handler(name: str, level: int, filename: str) -> TimedRotatingFileHandler:
    """
    创建配置的 TimedRotatingFileHandler 的帮助程序.
    使用默认的轮换格式：filename.YYYY-MM-DD
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
    """
    配置严格 JSON 日志记录，使用 structlog.
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
    # 我们为访问日志定义一个特定的记录器“api_traffic”
    # 如果我们不希望它在 info.log 中与应用程序日志混合，则该记录器不应传播到 root？
    # 用户请求单独的文件。
    # 中间件将使用 logger.bind(type="access") 或 structlog.get_logger("api_traffic")

    traffic_logger = logging.getLogger("api_traffic")
    traffic_logger.setLevel(logging.INFO)
    traffic_logger.propagate = (
        False  # 停止传递给 root （因此如果不需要，它不会在 info.log 中重复，但通常 info 包含所有内容）
    )
    # 如果用户想要分开，让我们关闭传播。

    traffic_handler = get_file_handler("traffic_handler", logging.INFO, "api_traffic.log")
    traffic_handler.setFormatter(file_formatter)
    traffic_logger.addHandler(traffic_handler)

    # 如果是本地的话，还要将标准输出添加到流量记录器中吗？

    if settings.ENVIRONMENT == "local":
        traffic_logger.addHandler(stream_handler)

    # 排除 uvicorn、sqlalchemy 的日志

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = structlog.get_logger()
# 公开访问日志的特定记录器

access_logger = structlog.get_logger("api_traffic")
