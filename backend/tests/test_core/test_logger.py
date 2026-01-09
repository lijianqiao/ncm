"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_logger.py
@DateTime: 2026-01-05 00:00:00
@Docs: 日志模块单元测试.
"""

import gzip
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

import app.core.logger as logger_module
from app.core.config import settings


def test_namer_adds_gz_suffix() -> None:
    assert logger_module.namer("logs/info.log.2026-01-01") == "logs/info.log.2026-01-01.gz"


def test_rotator_compresses_and_removes_source(tmp_path: Path) -> None:
    source = tmp_path / "a.log"
    dest = tmp_path / "a.log.gz"

    source.write_bytes("你好".encode())
    logger_module.rotator(str(source), str(dest))

    assert not source.exists()
    assert dest.exists()

    with gzip.open(dest, "rb") as f:
        assert f.read().decode("utf-8") == "你好"


def test_get_file_handler_sets_rotator_and_namer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logger_module, "LOG_DIR", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)

    handler = logger_module.get_file_handler("x", logging.INFO, "info.log")
    assert isinstance(handler, TimedRotatingFileHandler)
    assert handler.level == logging.INFO
    assert handler.rotator is logger_module.rotator  # type: ignore[comparison-overlap]
    assert handler.namer is logger_module.namer  # type: ignore[comparison-overlap]


def test_setup_logging_local_adds_stream_to_traffic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logger_module, "LOG_DIR", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)

    old_env = settings.ENVIRONMENT

    root_logger = logging.getLogger()
    old_root_handlers = list(root_logger.handlers)
    old_root_level = root_logger.level

    traffic_logger = logging.getLogger("api_traffic")
    old_traffic_handlers = list(traffic_logger.handlers)
    old_traffic_propagate = traffic_logger.propagate

    try:
        settings.ENVIRONMENT = "local"
        logger_module.setup_logging()

        assert len(root_logger.handlers) >= 3

        # traffic logger 不传播到 root
        assert traffic_logger.propagate is False

        # local 环境会把 stdout handler 也加到 traffic logger
        assert any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in traffic_logger.handlers)

    finally:
        settings.ENVIRONMENT = old_env
        root_logger.handlers = old_root_handlers
        root_logger.setLevel(old_root_level)
        traffic_logger.handlers = old_traffic_handlers
        traffic_logger.propagate = old_traffic_propagate


def test_setup_logging_non_local_no_stream_for_traffic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logger_module, "LOG_DIR", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)

    old_env = settings.ENVIRONMENT

    root_logger = logging.getLogger()
    old_root_handlers = list(root_logger.handlers)
    old_root_level = root_logger.level

    traffic_logger = logging.getLogger("api_traffic")
    old_traffic_handlers = list(traffic_logger.handlers)
    old_traffic_propagate = traffic_logger.propagate

    try:
        settings.ENVIRONMENT = "production"
        logger_module.setup_logging()

        assert traffic_logger.propagate is False
        assert not any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in traffic_logger.handlers)

    finally:
        settings.ENVIRONMENT = old_env
        root_logger.handlers = old_root_handlers
        root_logger.setLevel(old_root_level)
        traffic_logger.handlers = old_traffic_handlers
        traffic_logger.propagate = old_traffic_propagate
