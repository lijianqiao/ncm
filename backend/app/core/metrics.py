"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: metrics.py
@DateTime: 2025-12-30 16:20:00
@Docs: Prometheus 指标收集模块 (Prometheus Metrics).
"""

from prometheus_client import Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# 定义指标
REQUEST_COUNT = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求延迟 (秒)",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

LOGIN_ATTEMPTS = Counter(
    "login_attempts_total",
    "登录尝试总数",
    ["status"],  # success / failure
)

ACTIVE_USERS = Counter(
    "active_users_total",
    "活跃用户总数",
)


def record_request_metrics(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """记录请求指标。

    Args:
        method (str): HTTP 方法。
        endpoint (str): 端点路径。
        status_code (int): HTTP 状态码。
        duration (float): 请求处理时长（秒）。

    Returns:
        None: 无返回值。
    """
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def record_login_attempt(success: bool) -> None:
    """记录登录尝试。

    Args:
        success (bool): 是否成功。

    Returns:
        None: 无返回值。
    """
    LOGIN_ATTEMPTS.labels(status="success" if success else "failure").inc()


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus 指标端点。

    Args:
        request (Request): FastAPI 请求对象。

    Returns:
        Response: Prometheus 指标文本响应。
    """
    return Response(content=generate_latest(), media_type="text/plain")
