"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: exception_handlers.py
@DateTime: 2025-12-30 15:23:00
@Docs: 全局异常处理器 (Global Exception Handlers).
"""

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.exceptions import CustomException
from app.core.logger import logger


def _format_validation_errors(errors: Sequence[Any]) -> list[dict]:
    """
    格式化验证错误列表，提取更友好的错误信息。
    """
    formatted = []
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "验证错误")
        # 提取自定义消息 (去除 "Value error, " 前缀)
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        formatted.append({"field": field, "message": msg})
    return formatted


async def custom_exception_handler(request: Request, exc: CustomException):
    """
    自定义业务异常处理器。
    """
    return JSONResponse(
        status_code=exc.code,
        content={"error_code": exc.code, "message": exc.message, "details": exc.details},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    请求参数验证异常处理器。
    """
    errors = _format_validation_errors(exc.errors())

    try:
        client_ip = request.client.host if request.client else None
    except Exception:
        client_ip = None

    logger.warning(
        "参数验证错误",
        error_code=422,
        http_method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        details=errors,
    )
    return JSONResponse(
        status_code=422,
        content={"error_code": 422, "message": "参数验证错误", "details": errors},
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """
    Pydantic 模型验证异常处理器 (捕获 Schema 层校验错误)。
    """
    errors = _format_validation_errors(exc.errors())

    try:
        client_ip = request.client.host if request.client else None
    except Exception:
        client_ip = None

    logger.warning(
        "数据验证错误",
        error_code=422,
        http_method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        details=errors,
    )
    return JSONResponse(
        status_code=422,
        content={"error_code": 422, "message": "数据验证错误", "details": errors},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    通用异常处理器，捕获所有未处理的异常。

    生产环境中不暴露详细错误信息，仅返回统一的 500 错误。
    """
    try:
        client_ip = request.client.host if request.client else None
    except Exception:
        client_ip = None

    logger.error(
        "未处理的异常",
        error_type=type(exc).__name__,
        error_message=str(exc),
        http_method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error_code": 500, "message": "服务器内部错误", "details": None},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册所有全局异常处理器。
    """
    app.add_exception_handler(CustomException, custom_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, generic_exception_handler)  # 通用异常处理器（兜底）
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)  # type: ignore
