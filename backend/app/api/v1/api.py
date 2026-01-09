"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: api.py
@DateTime: 2025-12-30 15:30:00
@Docs: 动态 API 路由注册模块 (Dynamic API discovery).
"""

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import SessionDep
from app.api.v1 import endpoints
from app.core.cache import redis_client
from app.core.logger import logger

api_router = APIRouter()


@api_router.get("/health")
async def health_check(db: SessionDep):
    """
    健康检查接口 (Database & Cache Check).
    """
    health_status = {"status": "ok", "database": "unknown", "cache": "unknown"}

    # 检查数据库
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"

    # 检查 Redis
    try:
        if redis_client:
            await redis_client.ping()  # type: ignore
            health_status["cache"] = "connected"
        else:
            health_status["cache"] = "disabled"
    except Exception as e:
        logger.error(f"Redis 健康检查失败: {e}")
        health_status["cache"] = "disconnected"
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=health_status)


def auto_include_routers() -> None:
    """
    自动扫描 app.api.v1.endpoints 包下的所有模块，
    如果模块中有 'router' 属性，则注册到 api_router。
    默认前缀为模块名 (例如 auth.py -> /auth)。
    """
    package_name = endpoints.__name__
    package_path = Path(endpoints.__file__).parent

    registered_count = 0
    for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
        full_module_name = f"{package_name}.{module_name}"
        try:
            module: ModuleType = importlib.import_module(full_module_name)
            if hasattr(module, "router"):
                router_instance = module.router
                tag_name = module_name.capitalize()
                prefix = f"/{module_name}"

                api_router.include_router(router_instance, prefix=prefix, tags=[tag_name])
                registered_count += 1
                logger.debug(f"已注册路由: {prefix}")
        except Exception as e:
            logger.error(f"加载路由失败 {full_module_name}: {e}")

    logger.info(f"自动注册了 {registered_count} 个 API 路由")


# 执行自动注册
auto_include_routers()
