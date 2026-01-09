"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: main.py
@DateTime: 2025-12-30 12:50:00
@Docs: 应用程序入口 (Main Application Entry).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.api import api_router
from app.core.cache import close_redis, init_redis
from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.exception_handlers import register_exception_handlers
from app.core.logger import logger, setup_logging
from app.core.metrics import metrics_endpoint
from app.core.middleware import RequestLogMiddleware
from app.core.permissions import validate_no_magic_permission_strings
from app.core.rate_limiter import limiter
from app.subscribers.log_subscriber import register_log_subscribers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理: 启动与关闭事件。
    """
    setup_logging()
    logger.info("服务正在启动...")

    # 初始化 Redis
    await init_redis()

    # 启动期校验：禁止权限码魔法字符串
    validate_no_magic_permission_strings()

    # 注册事件订阅者
    register_log_subscribers()

    yield

    # 尽量等待审计日志等事件处理完成
    try:
        await event_bus.drain(timeout=5.0)
    except Exception as e:
        logger.warning(f"事件总线 drain 失败: {e}")

    # 关闭 Redis
    await close_redis()
    logger.info("服务正在关闭...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    default_response_class=JSONResponse,
)

# 配置 CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 添加请求日志中间件
app.add_middleware(RequestLogMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册限流器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 注册 Prometheus 指标端点 (不走 API 路由前缀)
app.add_route("/metrics", metrics_endpoint, methods=["GET"])
