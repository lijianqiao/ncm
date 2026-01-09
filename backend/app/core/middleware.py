"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: middleware.py
@DateTime: 2025-12-30 12:45:00
@Docs: 中间件：请求ID记录与日志 (Request Log Middleware).
       使用事件总线发布操作日志事件。
"""

import json
import re
import time
from typing import Any

import uuid6
from starlette.datastructures import Headers, QueryParams
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.event_bus import OperationLogEvent, event_bus
from app.core.logger import access_logger
from app.core.metrics import record_request_metrics


class RequestLogMiddleware:
    """全局请求日志中间件（ASGI 级别）。"""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        clear_contextvars()

        headers = Headers(scope=scope)
        request_id = headers.get("X-Request-ID") or str(uuid6.uuid7())
        bind_contextvars(request_id=request_id)

        method = (scope.get("method") or "").upper()
        path = scope.get("path") or ""
        query_string_raw: bytes = scope.get("query_string") or b""
        query_string = query_string_raw.decode("latin-1")

        client = scope.get("client")
        client_ip = client[0] if isinstance(client, (list, tuple)) and client else "unknown"

        request_body_buf = bytearray()
        request_body_truncated = False
        request_headers = headers
        request_content_type = (request_headers.get("content-type") or "").lower()
        user_agent = request_headers.get("user-agent")

        response_status_code: int | None = None
        response_headers: Headers | None = None
        response_body_buf = bytearray()
        response_body_truncated = False

        async def receive_wrapper() -> dict[str, Any]:
            nonlocal request_body_truncated
            message = await receive()
            if message.get("type") == "http.request" and method != "GET":
                body = message.get("body", b"")
                if body:
                    if len(request_body_buf) < _MAX_CAPTURE_BYTES:
                        remaining = _MAX_CAPTURE_BYTES - len(request_body_buf)
                        request_body_buf.extend(body[:remaining])
                        if len(body) > remaining:
                            request_body_truncated = True
                    else:
                        request_body_truncated = True
            return message

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_status_code, response_headers, response_body_truncated

            if message.get("type") == "http.response.start":
                response_status_code = int(message.get("status") or 500)
                raw_headers = message.get("headers") or []
                response_headers = Headers(raw=raw_headers)

                # 注入 X-Request-ID
                new_headers = list(raw_headers)
                new_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = new_headers

            elif message.get("type") == "http.response.body":
                if response_headers is not None:
                    content_type = (response_headers.get("content-type") or "").lower()
                    if "application/json" in content_type:
                        body = message.get("body", b"")
                        if body:
                            if len(response_body_buf) < _MAX_CAPTURE_BYTES:
                                remaining = _MAX_CAPTURE_BYTES - len(response_body_buf)
                                response_body_buf.extend(body[:remaining])
                                if len(body) > remaining:
                                    response_body_truncated = True
                            else:
                                response_body_truncated = True

            await send(message)

        start_time = time.perf_counter()
        await self.app(scope, receive_wrapper, send_wrapper)
        process_time = time.perf_counter() - start_time

        status_code = int(response_status_code or 500)

        # Prometheus 指标
        try:
            if not _is_probe_path(path):
                record_request_metrics(method, _metrics_endpoint(scope, path), status_code, process_time)
        except Exception:
            pass

        # 记录请求完成日志 (File Log)
        if not _is_probe_path(path):
            access_logger.info(
                "API 访问",
                http_method=method,
                url=_build_full_url(scope, query_string),
                path=path,
                query=query_string,
                status_code=status_code,
                client_ip=client_ip,
                latency=f"{process_time:.4f}s",
            )

            # [Audit] 发布操作日志事件
            # 排除 GET 请求 和 登录接口 (Login 由 AuthService 记录)
            state = scope.get("state")
            user_id_value = _get_state_value(state, "user_id")
            username_value = _get_state_value(state, "username")
            if method != "GET" and "/auth/login" not in path and user_id_value:
                params = _build_request_params_asgi(
                    path=path,
                    query_string_raw=query_string_raw,
                    path_params=scope.get("path_params") or {},
                    method=method,
                    request_content_type=request_content_type,
                    request_body=bytes(request_body_buf),
                    request_body_truncated=request_body_truncated,
                )
                response_result = _build_response_result_asgi(
                    path=path,
                    response_headers=response_headers,
                    response_body=bytes(response_body_buf),
                    response_body_truncated=response_body_truncated,
                )

                await event_bus.publish(
                    OperationLogEvent(
                        user_id=str(user_id_value),
                        username=str(username_value or ""),
                        ip=client_ip if client_ip != "unknown" else None,
                        method=method,
                        path=path,
                        status_code=status_code,
                        process_time=process_time,
                        params=params,
                        response_result=response_result,
                        user_agent=user_agent,
                    )
                )


_MAX_CAPTURE_BYTES = 20_000


def _is_probe_path(path: str) -> bool:
    return path in ("/metrics", "/health", "/api/v1/health")


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_INT_RE = re.compile(r"^\d+$")


def _metrics_endpoint(scope: dict[str, Any], path: str) -> str:
    """用于 Prometheus 的 endpoint label。

    优先使用路由模板（/users/{id}），否则做简单归一化。
    """

    try:
        route = scope.get("route")
        if route is not None:
            route_path = getattr(route, "path", None)
            if isinstance(route_path, str) and route_path:
                return route_path
    except Exception:
        pass

    parts = [p for p in path.split("/") if p]
    normalized: list[str] = []
    for p in parts:
        if _UUID_RE.match(p) or _INT_RE.match(p):
            normalized.append("{id}")
        else:
            normalized.append(p)

    return "/" + "/".join(normalized)


def _get_state_value(state: Any, key: str) -> Any | None:
    if state is None:
        return None
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)


def _is_sensitive_path(path: str) -> bool:
    lowered = path.lower()
    if "/auth/" in lowered:
        return True
    if "password" in lowered:
        return True
    return False


def _safe_json_loads(raw: bytes) -> Any | None:
    try:
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text)
    except Exception:
        return None


_SENSITIVE_KEYS = {
    "password",
    "old_password",
    "new_password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "phone",
    "mobile",
    "email",
}


def _mask_string_value(key: str, value: str) -> str:
    k = key.lower()
    if "password" in k or "token" in k or k == "authorization":
        return "***"

    if k in ("phone", "mobile"):
        # +8613800138000 -> +86138****8000
        if len(value) <= 7:
            return "***"
        return value[:5] + "****" + value[-4:]

    if k == "email":
        # a***@xx.com
        if "@" not in value:
            return "***"
        local, domain = value.split("@", 1)
        if not local:
            return "***@" + domain
        return local[:1] + "***@" + domain

    return "***"


def _mask_sensitive_data(obj: Any) -> Any:
    """递归脱敏 JSON 数据。

    目标：尽量不改变结构，只替换敏感值。
    """

    if isinstance(obj, dict):
        masked: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            low = key.lower()
            if low in _SENSITIVE_KEYS or any(x in low for x in ("password", "token")):
                if v is None:
                    masked[key] = None
                elif isinstance(v, str):
                    masked[key] = _mask_string_value(low, v)
                else:
                    masked[key] = "***"
            else:
                masked[key] = _mask_sensitive_data(v)
        return masked

    if isinstance(obj, list):
        return [_mask_sensitive_data(x) for x in obj]

    return obj


def _build_request_params_asgi(
    *,
    path: str,
    query_string_raw: bytes,
    path_params: dict[str, Any],
    method: str,
    request_content_type: str,
    request_body: bytes,
    request_body_truncated: bool,
) -> dict[str, Any] | None:
    data: dict[str, Any] = {}

    try:
        if query_string_raw:
            data["query"] = dict(QueryParams(query_string_raw))
    except Exception:
        pass

    try:
        if path_params:
            data["path"] = dict(path_params)
    except Exception:
        pass

    if method != "GET":
        if _is_sensitive_path(path):
            data["body"] = {"_filtered": True}
        else:
            if request_body_truncated:
                data["body"] = {"_truncated": True}
            elif request_body:
                if "application/json" in request_content_type:
                    parsed = _safe_json_loads(request_body)
                    data["body"] = _mask_sensitive_data(parsed) if parsed is not None else {"_unparsed": True}
                else:
                    data["body"] = {"_non_json": True}

    return data or None


def _build_response_result_asgi(
    *,
    path: str,
    response_headers: Headers | None,
    response_body: bytes,
    response_body_truncated: bool,
) -> Any | None:
    if _is_sensitive_path(path):
        return {"_filtered": True}

    if response_headers is None:
        return None

    content_type = (response_headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        # 走摘要：非 JSON 仅记录类型，避免 response_result 为 null 又无意义
        return {"_non_json": True, "content_type": content_type or None}

    if response_body_truncated:
        return {"_truncated": True}

    if not response_body:
        return None

    parsed = _safe_json_loads(response_body)
    return _mask_sensitive_data(parsed) if parsed is not None else {"_unparsed": True}


def _build_full_url(scope: dict[str, Any], query_string: str) -> str:
    try:
        scheme = scope.get("scheme") or "http"
        server = scope.get("server")
        host = "localhost"
        port_part = ""
        if isinstance(server, (list, tuple)) and len(server) >= 2:
            host = str(server[0])
            port = int(server[1])
            if (scheme == "http" and port != 80) or (scheme == "https" and port != 443):
                port_part = f":{port}"

        path = scope.get("path") or ""
        if query_string:
            return f"{scheme}://{host}{port_part}{path}?{query_string}"
        return f"{scheme}://{host}{port_part}{path}"
    except Exception:
        path = scope.get("path") or ""
        return path
