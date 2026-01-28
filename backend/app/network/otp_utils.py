"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: otp_utils.py
@DateTime: 2026-01-20 00:55:00
@Docs: OTP 辅助工具（缓存读取与异常封装）。

统一的 OTP 认证处理逻辑，供 async_tasks 和 nornir_tasks 共用。
包含 OTP 重试包装器，简化认证失败后的重试流程。
"""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from uuid import UUID

from app.core.config import settings
from app.core.exceptions import OTPRequiredException
from app.core.otp_service import otp_service

T = TypeVar("T")


async def resolve_otp_password(
    auth_type: str | None,
    host_data: dict[str, Any],
) -> str | None:
    """
    根据认证类型解析 OTP 密码（统一入口）。

    Args:
        auth_type: 认证类型 (static/otp_seed/otp_manual)
        host_data: 包含 otp_seed_encrypted, dept_id, device_group, device_id 等

    Returns:
        str | None: 解析后的密码，static 类型返回 None（使用原密码）

    Raises:
        OTPRequiredException: otp_manual 类型且缓存中无 OTP 时抛出
        ValueError: 缺少必要参数时抛出
    """
    if auth_type == "otp_seed":
        encrypted_seed = host_data.get("otp_seed_encrypted")
        if not encrypted_seed:
            raise ValueError("缺少 OTP 种子，无法生成验证码")
        return otp_service.generate_totp(str(encrypted_seed))

    if auth_type == "otp_manual":
        dept_id_raw = host_data.get("dept_id")
        device_group = host_data.get("device_group")
        if not dept_id_raw or not device_group:
            raise ValueError("缺少 OTP 所需的部门/分层信息，无法获取验证码")

        dept_id = UUID(str(dept_id_raw))
        failed_id = host_data.get("device_id") or host_data.get("name", "unknown")

        otp_code = await otp_service.get_cached_otp(dept_id, str(device_group))
        if not otp_code:
            raise OTPRequiredException(
                dept_id=dept_id,
                device_group=str(device_group),
                failed_devices=[str(failed_id)],
                message="需要输入 OTP 验证码",
            )
        return otp_code

    # static 或其他类型，返回 None 表示使用原密码
    return None


def resolve_otp_password_sync(
    auth_type: str | None,
    host_data: dict[str, Any],
) -> str | None:
    """
    同步版 OTP 密码解析（使用 run_async 包装）。

    用于 Nornir 同步任务中。
    """
    from app.celery.base import run_async

    return run_async(resolve_otp_password(auth_type, host_data))


def build_otp_required_exception(
    dept_id: UUID,
    device_group: str,
    failed_id: str,
    message: str = "需要输入 OTP 验证码",
) -> OTPRequiredException:
    return OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=[str(failed_id)],
        message=message,
    )


async def get_manual_otp_or_raise(
    dept_id: UUID,
    device_group: str,
    failed_id: str,
) -> str:
    otp_code = await otp_service.get_cached_otp(dept_id, str(device_group))
    if not otp_code:
        raise build_otp_required_exception(dept_id, str(device_group), failed_id)
    return otp_code


async def get_seed_otp(encrypted_seed: str) -> str:
    if not encrypted_seed:
        raise ValueError("缺少 OTP 种子，无法生成验证码")
    return otp_service.generate_totp(str(encrypted_seed))


async def invalidate_manual_otp(dept_id: UUID, device_group: str) -> None:
    await otp_service.invalidate_otp(dept_id, str(device_group))


async def wait_and_retry_otp(
    dept_id: UUID,
    device_group: str,
    timeout: int | None = None,
) -> str | None:
    """
    等待新 OTP 输入（用于断点续传）。

    先失效旧 OTP 缓存，然后轮询等待前端输入新 OTP。
    适用于任务执行中 OTP 过期/失效的场景。

    Args:
        dept_id: 部门 ID
        device_group: 设备分组
        timeout: 超时时间（秒），默认使用 OTP_WAIT_TIMEOUT_SECONDS (60s)

    Returns:
        新的 OTP 验证码，超时返回 None
    """
    from app.core.logger import logger

    # 1. 先失效旧 OTP 缓存
    await invalidate_manual_otp(dept_id, str(device_group))

    logger.info(
        "OTP 已失效，开始等待新 OTP 输入",
        dept_id=str(dept_id),
        device_group=device_group,
        timeout=timeout,
    )

    # 2. 轮询等待新 OTP
    new_otp = await otp_service.wait_for_otp(dept_id, str(device_group), timeout=timeout)

    if new_otp:
        logger.info(
            "收到新 OTP，准备重试",
            dept_id=str(dept_id),
            device_group=device_group,
        )
    else:
        logger.warning(
            "等待新 OTP 超时",
            dept_id=str(dept_id),
            device_group=device_group,
            timeout=timeout,
        )

    return new_otp


def wait_and_retry_otp_sync(
    dept_id: UUID,
    device_group: str,
    timeout: int | None = None,
) -> str | None:
    """
    同步版等待新 OTP 输入（使用 run_async 包装）。

    用于 Nornir 同步任务中。
    """
    from app.celery.base import run_async

    return run_async(wait_and_retry_otp(dept_id, device_group, timeout=timeout))


async def handle_otp_auth_failure(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> str:
    """
    处理 OTP 认证失败：失效旧缓存 → 立即返回 428 让前端重新输入。

    仅适用于 auth_type == 'otp_manual' 的设备。
    立即抛出 OTPRequiredException，不阻塞等待。

    Args:
        host_data: 包含 auth_type, dept_id, device_group 等
        original_error: 原始认证错误
        failed_devices: 失败设备列表

    Raises:
        OTPRequiredException: OTP 认证失败，需要前端重新输入
        原始异常: 非 otp_manual 设备
    """
    from app.core.logger import logger

    auth_type = host_data.get("auth_type")
    if auth_type != "otp_manual":
        # 非 otp_manual 设备，直接抛出原始错误
        raise original_error

    dept_id_raw = host_data.get("dept_id")
    device_group = host_data.get("device_group")

    if not dept_id_raw or not device_group:
        raise original_error

    dept_id = UUID(str(dept_id_raw))
    device_id = host_data.get("device_id") or host_data.get("name", "unknown")

    # 1. 失效旧 OTP 缓存
    try:
        await invalidate_manual_otp(dept_id, str(device_group))
        logger.info(
            "OTP 认证失败，已失效旧缓存，立即返回 428",
            dept_id=str(dept_id),
            device_group=device_group,
            device_id=str(device_id),
        )
    except Exception as e:
        logger.warning(f"失效 OTP 缓存失败: {e}")

    # 2. 立即抛出异常，让前端重新输入 OTP
    all_failed = failed_devices or [str(device_id)]
    raise OTPRequiredException(
        dept_id=dept_id,
        device_group=str(device_group),
        failed_devices=all_failed,
        message="OTP 认证失败，请重新输入验证码",
    )


def handle_otp_auth_failure_sync(
    host_data: dict,
    original_error: Exception,
    *,
    failed_devices: list[str] | None = None,
) -> str:
    """
    同步版 OTP 认证失败处理（使用 run_async 包装）。

    用于 Nornir 同步任务中。
    """
    from app.celery.base import run_async

    return run_async(handle_otp_auth_failure(host_data, original_error, failed_devices=failed_devices))


async def with_otp_retry[T](
    host_data: dict[str, Any],
    execute_fn: Callable[[], Awaitable[T]],
    retry_fn: Callable[[str], Awaitable[T]],
    *,
    timeout: int | None = None,
) -> T:
    """
    带 OTP 重试的执行包装器。

    用于简化 OTP 认证失败后的重试逻辑：
    1. 执行主函数
    2. 如果认证失败且是 otp_manual 类型，等待新 OTP
    3. 使用新 OTP 执行重试函数
    4. 如果无法恢复，抛出 OTPRequiredException

    Args:
        host_data: 主机数据，包含 auth_type, dept_id, device_group 等
        execute_fn: 主执行函数（无参数，返回结果）
        retry_fn: 重试函数（接收新 OTP，返回结果）
        timeout: OTP 等待超时时间（秒），默认使用 OTP_WAIT_TIMEOUT_SECONDS

    Returns:
        T: 执行结果

    Raises:
        OTPRequiredException: 无法恢复时抛出
        Exception: 其他执行异常

    Example:
        ```python
        async def execute():
            async with pool.acquire(...) as conn:
                return await conn.send_command(command)

        async def retry_with_otp(new_otp: str):
            async with pool.acquire(..., password=new_otp) as conn:
                return await conn.send_command(command)

        result = await with_otp_retry(
            host_data,
            execute_fn=execute,
            retry_fn=retry_with_otp,
        )
        ```
    """
    from app.core.logger import logger
    from scrapli.exceptions import ScrapliAuthenticationFailed

    effective_timeout = timeout or getattr(settings, "OTP_WAIT_TIMEOUT_SECONDS", 60)

    try:
        return await execute_fn()
    except ScrapliAuthenticationFailed as e:
        auth_type = host_data.get("auth_type")
        if auth_type != "otp_manual":
            # 非 otp_manual 设备，直接抛出异常
            raise

        dept_id_raw = host_data.get("dept_id")
        device_group = host_data.get("device_group")

        if not dept_id_raw or not device_group:
            # 缺少必要信息，无法重试
            await handle_otp_auth_failure(host_data, e)
            raise

        dept_id = UUID(str(dept_id_raw))
        device_name = host_data.get("device_name") or host_data.get("name", "unknown")

        logger.info(
            "认证失败，等待新 OTP",
            host=device_name,
            dept_id=str(dept_id),
            device_group=device_group,
            timeout=effective_timeout,
        )

        # 等待新 OTP
        new_otp = await wait_and_retry_otp(dept_id, str(device_group), timeout=effective_timeout)

        if new_otp:
            logger.info("收到新 OTP，执行重试", host=device_name)
            return await retry_fn(new_otp)

        # 等待超时，无法恢复
        await handle_otp_auth_failure(host_data, e)
        raise
