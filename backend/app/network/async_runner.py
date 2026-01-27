"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: async_runner.py
@DateTime: 2026-01-14 00:26:00
@Docs: Nornir 异步运行器，替代 ThreadedRunner 实现真正的 asyncio 并发。

使用 asyncio.Semaphore 控制最大并发数，配合 Scrapli Async 驱动实现高效网络自动化。
"""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any

from nornir.core.task import AggregatedResult, MultiResult, Result

from app.core.config import settings
from app.core.exceptions import OTPRequiredException
from app.core.logger import celery_details_logger, logger

if TYPE_CHECKING:
    from nornir.core.inventory import Host, Inventory

type AsyncTaskFn = Callable[["Host"], Coroutine[Any, Any, Any]]
"""异步任务函数类型：接收 Host 返回协程。"""

type ProgressCallback = Callable[[str, Result], Awaitable[None] | None]
"""进度回调类型：接收 host_name 和 Result，返回可选的 awaitable。"""

type HostsDict = dict[str, "Host"]
"""主机字典类型。"""


class AsyncRunner:
    """
    异步任务运行器。

    替换 Nornir 默认的 ThreadedRunner，使用 asyncio 事件循环实现真正的异步并发。
    适用于大批量设备操作场景，显著降低线程开销。

    Attributes:
        semaphore_limit: 最大并发连接数（通过 asyncio.Semaphore 控制）
        max_retries: 失败重试次数（0 表示不重试）
        retry_delay: 重试间隔（秒）
    """

    def __init__(
        self,
        num_workers: int | None = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ):
        """
        初始化异步运行器。

        Args:
            num_workers: 最大并发数，默认从配置读取 ASYNC_SSH_SEMAPHORE
            max_retries: 失败重试次数（默认 0 不重试）
            retry_delay: 重试间隔秒数（默认 1.0）
        """
        self.semaphore_limit = num_workers or settings.ASYNC_SSH_SEMAPHORE
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def run(
        self,
        task: AsyncTaskFn,
        hosts: HostsDict,
        **kwargs: Any,
    ) -> AggregatedResult:
        """
        同步入口，供 Nornir.run() 兼容调用。

        内部使用 asyncio.run() 启动异步执行。

        Args:
            task: 异步任务函数，签名为 async def task(host: Host) -> Any
            hosts: 主机字典 {host_name: Host}
            **kwargs: 传递给任务函数的额外参数

        Returns:
            AggregatedResult: Nornir 标准聚合结果
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("当前存在运行中的事件循环，请使用 await run_async_tasks(...) 调用异步执行入口。")
        return asyncio.run(self._run_async(task, hosts, **kwargs))

    async def _run_async(
        self,
        task: AsyncTaskFn,
        hosts: HostsDict,
        progress_callback: ProgressCallback | None = None,
        otp_wait_timeout: int | None = None,
        **kwargs: Any,
    ) -> AggregatedResult:
        """
        异步执行主体。

        使用 Semaphore 控制并发，支持可配置的重试机制和 OTP 断点续传。

        Args:
            task: 异步任务函数
            hosts: 主机字典
            progress_callback: 可选的进度回调
            otp_wait_timeout: OTP 等待超时时间（秒），设置后支持断点续传
            **kwargs: 额外参数

        Returns:
            AggregatedResult: 聚合结果
        """
        from uuid import UUID

        from app.network.otp_utils import wait_and_retry_otp

        task_name = getattr(task, "__name__", "async_task")
        results = AggregatedResult(task_name)
        semaphore = asyncio.Semaphore(self.semaphore_limit)

        # OTP 超时标记：一旦某个设备等待 OTP 超时，取消剩余任务
        otp_timeout_event = asyncio.Event()

        async def _execute_host(host: "Host") -> tuple[str, Result]:
            """单设备执行（带信号量控制、OTP 等待和可选重试）。"""
            last_exception: Exception | None = None

            for attempt in range(self.max_retries + 1):
                # 检查是否已有 OTP 超时，跳过执行
                if otp_timeout_event.is_set():
                    return host.name, Result(
                        host=host,
                        result={"success": False, "otp_timeout": True, "skipped": True},
                        failed=True,
                    )

                try:
                    async with semaphore:
                        logger.debug("开始执行异步任务", host=host.name, task=task_name, attempt=attempt + 1)
                        result_data = await task(host, **kwargs)
                        return host.name, Result(host=host, result=result_data)
                except OTPRequiredException as e:
                    # OTP 异常：尝试等待新 OTP
                    if otp_wait_timeout and otp_wait_timeout > 0:
                        dept_id_raw = host.data.get("dept_id")
                        device_group = host.data.get("device_group")

                        if dept_id_raw and device_group:
                            logger.info(
                                "OTP 异常，开始等待新 OTP",
                                host=host.name,
                                dept_id=str(dept_id_raw),
                                device_group=device_group,
                                timeout=otp_wait_timeout,
                            )

                            new_otp = await wait_and_retry_otp(
                                UUID(str(dept_id_raw)),
                                str(device_group),
                                timeout=otp_wait_timeout,
                            )

                            if new_otp:
                                # 收到新 OTP，更新 host 密码并重试
                                host.password = new_otp
                                logger.info("收到新 OTP，准备重试", host=host.name)
                                continue  # 重新进入循环执行任务
                            else:
                                # 等待超时，设置超时标记
                                otp_timeout_event.set()
                                logger.warning("等待新 OTP 超时，终止剩余任务", host=host.name)
                                return host.name, Result(
                                    host=host,
                                    result={"success": False, "otp_timeout": True, "error": "等待 OTP 超时"},
                                    failed=True,
                                )

                    # 不等待或无法等待，直接返回 OTP 异常
                    return host.name, Result(host=host, exception=e, failed=True)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        logger.warning(
                            "任务失败，准备重试",
                            host=host.name,
                            task=task_name,
                            attempt=attempt + 1,
                            max_retries=self.max_retries,
                            error=str(e),
                        )
                        await asyncio.sleep(self.retry_delay)
                    else:
                        logger.error(
                            "任务执行失败",
                            host=host.name,
                            task=task_name,
                            error=str(e),
                            exc_info=True,
                        )
                        # 记录详细失败日志到 celery_details
                        celery_details_logger.warning(
                            "任务执行失败",
                            host=host.name,
                            task=task_name,
                            error=str(e),
                            error_type=type(e).__name__,
                        )

            return host.name, Result(host=host, exception=last_exception, failed=True)

        # 并行执行所有主机任务
        tasks = [asyncio.create_task(_execute_host(host)) for host in hosts.values()]
        for done in asyncio.as_completed(tasks):
            host_name, result = await done
            multi = MultiResult(host_name)
            multi.append(result)
            results[host_name] = multi
            if progress_callback:
                try:
                    logger.debug("准备调用进度回调", host=host_name)
                    maybe_awaitable = progress_callback(host_name, result)
                    if asyncio.iscoroutine(maybe_awaitable):
                        await maybe_awaitable
                    logger.debug("进度回调完成", host=host_name)
                except Exception as e:
                    logger.warning("进度回调失败", host=host_name, error=str(e), exc_info=True)

        # 统计
        failed_count = sum(1 for r in results.values() if r.failed)
        success_count = len(results) - failed_count
        celery_details_logger.info(
            "异步任务批量执行完成",
            task=task_name,
            total=len(results),
            success=success_count,
            failed=failed_count,
        )

        return results


async def run_async_tasks(
    hosts: "HostsDict | Inventory",
    task_fn: AsyncTaskFn,
    num_workers: int | None = None,
    progress_callback: ProgressCallback | None = None,
    otp_wait_timeout: int | None = None,
    **kwargs: Any,
) -> AggregatedResult:
    """
    独立的异步任务执行入口（不依赖 Nornir.run()）。

    这是推荐的异步执行方式，绕过 Nornir 的同步 Runner 协议限制。
    支持 OTP 断点续传：当 OTP 失效时等待新 OTP，超时后终止剩余任务。

    Args:
        hosts: Nornir Inventory 或主机字典
        task_fn: 异步任务函数，签名为 async def task(host: Host, **kwargs) -> Any
        num_workers: 最大并发数，默认从配置读取
        progress_callback: 可选的进度回调
        otp_wait_timeout: OTP 等待超时时间（秒），设置后支持断点续传
        **kwargs: 传递给任务函数的额外参数

    Returns:
        AggregatedResult: 标准聚合结果

    Example:
        ```python
        from app.network.async_runner import run_async_tasks
        from app.network.async_tasks import async_send_command

        nr = init_nornir_async_from_db(devices)
        results = await run_async_tasks(
            nr.inventory.hosts,
            async_send_command,
            command="display version",
            otp_wait_timeout=60,  # OTP 等待超时 60 秒
        )
        ```
    """
    # 处理 Inventory 对象
    if hasattr(hosts, "hosts"):
        hosts_dict: HostsDict = hosts.hosts  # type: ignore[union-attr]
    else:
        hosts_dict = hosts  # type: ignore[assignment]

    runner = AsyncRunner(num_workers=num_workers)
    return await runner._run_async(
        task_fn,
        hosts_dict,
        progress_callback=progress_callback,
        otp_wait_timeout=otp_wait_timeout,
        **kwargs,
    )


def run_async_tasks_sync(
    hosts: "HostsDict | Inventory",
    task_fn: AsyncTaskFn,
    num_workers: int | None = None,
    progress_callback: ProgressCallback | None = None,
    otp_wait_timeout: int | None = None,
    **kwargs: Any,
) -> AggregatedResult:
    """
    同步包装的异步任务执行入口（用于 Celery 等同步上下文）。

    内部使用 asyncio.run() 启动事件循环。

    Args:
        hosts: Nornir Inventory 或主机字典
        task_fn: 异步任务函数
        num_workers: 最大并发数
        progress_callback: 可选的进度回调
        otp_wait_timeout: OTP 等待超时时间（秒）
        **kwargs: 额外参数

    Returns:
        AggregatedResult: 标准聚合结果
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("当前存在运行中的事件循环，请使用 await run_async_tasks(...) 调用异步执行入口。")
    return asyncio.run(
        run_async_tasks(
            hosts,
            task_fn,
            num_workers,
            progress_callback=progress_callback,
            otp_wait_timeout=otp_wait_timeout,
            **kwargs,
        )
    )


class AsyncRunnerWithRetry(AsyncRunner):
    """
    带重试机制的异步运行器。

    继承 AsyncRunner，默认启用重试（max_retries=2）。
    """

    def __init__(
        self,
        num_workers: int | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ):
        """
        初始化带重试的异步运行器。

        Args:
            num_workers: 最大并发数
            max_retries: 最大重试次数（默认 2）
            retry_delay: 重试间隔秒数（默认 1.0）
        """
        super().__init__(num_workers, max_retries=max_retries, retry_delay=retry_delay)
