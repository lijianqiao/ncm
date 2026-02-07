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
from uuid import UUID

from nornir.core.task import AggregatedResult, MultiResult, Result

from app.core.config import settings
from app.core.exceptions import OTPRequiredException
from app.core.logger import celery_details_logger, celery_task_logger, logger
from app.core.otp import otp_coordinator

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
        max_retry_delay: float = 30.0,
        exponential_backoff: bool = True,
    ):
        """
        初始化异步运行器。

        Args:
            num_workers: 最大并发数，默认从配置读取 ASYNC_SSH_SEMAPHORE
            max_retries: 失败重试次数（默认 0 不重试）
            retry_delay: 初始重试间隔秒数（默认 1.0）
            max_retry_delay: 最大重试间隔秒数（默认 30.0）
            exponential_backoff: 是否启用指数退避（默认 True）
        """
        self.semaphore_limit = num_workers or settings.ASYNC_SSH_SEMAPHORE
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self.exponential_backoff = exponential_backoff

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
        celery_task_id: str | None = None,
        **kwargs: Any,
    ) -> AggregatedResult:
        """
        异步执行主体。

        使用 Semaphore 控制并发，支持 OTP 任务内等待机制。

        Args:
            task: 异步任务函数
            hosts: 主机字典
            progress_callback: 可选的进度回调
            otp_wait_timeout: OTP 等待超时时间（秒），兼容参数
            celery_task_id: Celery 任务 ID（用于写入 OTP 等待信号，通知轮询端点返回 428）
            **kwargs: 额外参数

        Returns:
            AggregatedResult: 聚合结果
        """
        task_name = getattr(task, "__name__", "async_task")
        results = AggregatedResult(task_name)
        semaphore = asyncio.Semaphore(self.semaphore_limit)

        # ===== OTP 共享等待机制 =====
        # 同一 credential_id 下所有设备共享一个 Redis 轮询和结果，
        # 避免 100 台设备各自轮询导致 Redis "Too many connections"。
        _otp_events: dict[str, asyncio.Event] = {}
        _otp_results: dict[str, str | None] = {}  # credential_id -> otp_code 或 None(超时)
        _otp_polling: set[str] = set()

        async def _poll_otp_once(cred_id_str: str, credential_id: UUID) -> None:
            """单个 Redis 轮询协程（每个 credential 最多一个）。"""
            poll_interval = 2
            waited = 0
            wait_timeout = settings.OTP_WAIT_TIMEOUT_SECONDS

            while waited < wait_timeout:
                await asyncio.sleep(poll_interval)
                waited += poll_interval
                try:
                    otp = await otp_coordinator.get_cached_otp(credential_id)
                    if otp:
                        _otp_results[cred_id_str] = otp
                        # 安全访问：event 可能被其他协程重置
                        evt = _otp_events.get(cred_id_str)
                        if evt:
                            evt.set()
                        return
                except Exception:
                    pass  # Redis 暂时不可用，继续重试

            # 超时
            _otp_results[cred_id_str] = None
            evt = _otp_events.get(cred_id_str)
            if evt:
                evt.set()

        async def _wait_for_shared_otp(credential_id: UUID) -> str | None:
            """等待新 OTP（共享：同一 credential 只有 1 个 Redis 轮询）。"""
            cred_str = str(credential_id)

            # 已有结果（之前的设备等到了或超时了）
            if cred_str in _otp_results:
                return _otp_results[cred_str]

            # 创建共享事件（确保始终存在）
            if cred_str not in _otp_events:
                _otp_events[cred_str] = asyncio.Event()

            # 如果没有轮询协程在跑，启动一个
            # 使用分布式锁保护 invalidate，防止跨 Celery 任务竞态清掉用户新输入的 OTP
            if cred_str not in _otp_polling:
                _otp_polling.add(cred_str)
                await otp_coordinator.safe_invalidate_and_poll(credential_id)
                asyncio.create_task(_poll_otp_once(cred_str, credential_id))

            # 所有设备等同一个事件（带超时保护）
            # 安全获取 event：可能在 await 期间被其他协程重置，需要重新获取
            evt = _otp_events.get(cred_str)
            if evt is None:
                # 极端竞态：event 被移除，重新创建
                evt = asyncio.Event()
                _otp_events[cred_str] = evt

            try:
                await asyncio.wait_for(
                    evt.wait(),
                    timeout=settings.OTP_WAIT_TIMEOUT_SECONDS + 5,  # 略大于轮询超时
                )
            except TimeoutError:
                pass

            return _otp_results.get(cred_str)

        async def _execute_host(host: "Host") -> tuple[str, Result]:
            """单设备执行（带信号量控制、OTP 等待和可选重试）。"""
            last_exception: Exception | None = None

            for attempt in range(self.max_retries + 1):
                try:
                    async with semaphore:
                        logger.debug("开始执行异步任务", host=host.name, task=task_name, attempt=attempt + 1)
                        result_data = await task(host, **kwargs)
                        return host.name, Result(host=host, result=result_data)
                except OTPRequiredException as e:
                    # OTP 过期：进入等待→重试循环（最多 3 轮）
                    # 每轮：等待用户输入新 OTP → 用新 OTP 重试 SSH → 成功则返回
                    # 如果重试又 OTP 过期，重置共享状态，进入下一轮等待
                    try:
                        credential_id_str = e.credential_id_str
                        if not credential_id_str:
                            return host.name, Result(
                                host=host,
                                result={"success": False, "error": str(e)},
                                failed=True,
                            )

                        credential_id = UUID(credential_id_str)
                        max_otp_rounds = 3
                        last_otp_error: Exception | None = e

                        for otp_round in range(max_otp_rounds):
                            # 写入等待信号 → 轮询端点返回 428 → 前端弹 OTP 输入
                            if celery_task_id:
                                await otp_coordinator.signal_otp_wait(
                                    celery_task_id,
                                    credential_id,
                                    credential_username=getattr(last_otp_error, "credential_username", None),
                                    credential_device_group=getattr(last_otp_error, "credential_device_group", None),
                                )

                            celery_task_logger.info(
                                "OTP 过期，等待用户输入新 OTP",
                                host=host.name,
                                credential_id=credential_id_str,
                                otp_round=otp_round + 1,
                            )

                            # 共享等待：同一 credential 只有 1 个 Redis 轮询
                            new_otp = await _wait_for_shared_otp(credential_id)

                            # 等待结束，清除信号
                            if celery_task_id:
                                await otp_coordinator.clear_otp_wait_signal(celery_task_id)

                            if not new_otp:
                                celery_task_logger.warning(
                                    "OTP 等待超时",
                                    host=host.name,
                                    credential_id=credential_id_str,
                                )
                                return host.name, Result(
                                    host=host,
                                    result={"success": False, "error": "等待 OTP 验证码超时"},
                                    failed=True,
                                )

                            # 收到新 OTP，重试连接
                            celery_task_logger.info(
                                "收到新 OTP，重试连接",
                                host=host.name,
                                otp_round=otp_round + 1,
                            )
                            host.data["otp_password_prefetched"] = new_otp
                            try:
                                async with semaphore:
                                    result_data = await task(host, **kwargs)
                                    return host.name, Result(host=host, result=result_data)
                            except OTPRequiredException as otp_retry_exc:
                                # 重试也 OTP 过期 → 重置共享状态，下一轮重新等待
                                last_otp_error = otp_retry_exc
                                cred_str = str(credential_id)
                                # 重置 event（不删除！）防止其他等待中的协程 KeyError
                                _otp_events[cred_str] = asyncio.Event()
                                _otp_results.pop(cred_str, None)
                                _otp_polling.discard(cred_str)
                                celery_task_logger.warning(
                                    "OTP 重试仍然过期，进入下一轮等待",
                                    host=host.name,
                                    otp_round=otp_round + 1,
                                )
                                continue
                            except Exception as retry_exc:
                                # 非 OTP 错误（连接超时等）→ 直接失败
                                celery_details_logger.error(
                                    "OTP 重试后仍然失败",
                                    host=host.name,
                                    error=str(retry_exc),
                                    error_type=type(retry_exc).__name__,
                                )
                                return host.name, Result(host=host, exception=retry_exc, failed=True)

                        # 3 轮都 OTP 过期 → 最终失败
                        return host.name, Result(
                            host=host,
                            result={"success": False, "error": "OTP 多次重试仍然失败"},
                            failed=True,
                        )
                    except Exception as otp_handler_exc:
                        # 兜底：OTP 处理流程内的非预期异常（如竞态 KeyError）
                        # 转为设备级别失败，不让整个任务崩溃
                        celery_details_logger.error(
                            "OTP 处理流程内部异常",
                            host=host.name,
                            error=str(otp_handler_exc),
                            error_type=type(otp_handler_exc).__name__,
                            exc_info=True,
                        )
                        return host.name, Result(
                            host=host,
                            result={"success": False, "error": f"OTP 处理异常: {otp_handler_exc}"},
                            failed=True,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        # 计算重试延迟（支持指数退避）
                        if self.exponential_backoff:
                            delay = min(self.retry_delay * (2**attempt), self.max_retry_delay)
                        else:
                            delay = self.retry_delay

                        celery_task_logger.warning(
                            "任务失败，准备重试",
                            host=host.name,
                            task=task_name,
                            attempt=attempt + 1,
                            max_retries=self.max_retries,
                            retry_delay=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        # 预期的网络自动化错误（设备不可达、超时等）降级为 warning
                        _EXPECTED_NETWORK_ERRORS = (
                            "ScrapliAuthenticationFailed",
                            "ScrapliTimeout",
                            "ConnectionLost",
                            "ConnectionRefused",
                            "ScrapliConnectionNotOpened",
                        )
                        error_type_name = type(e).__name__
                        if error_type_name in _EXPECTED_NETWORK_ERRORS:
                            celery_details_logger.warning(
                                "设备连接失败",
                                host=host.name,
                                task=task_name,
                                error=str(e),
                                error_type=error_type_name,
                            )
                        else:
                            celery_details_logger.error(
                                "任务执行失败",
                                host=host.name,
                                task=task_name,
                                error=str(e),
                                error_type=error_type_name,
                                exc_info=True,
                            )

            return host.name, Result(host=host, exception=last_exception, failed=True)

        # 并行执行所有主机任务（按设备分组创建，避免内存问题）
        GROUP_BATCH_SIZE = 100  # 每组内分批大小
        hosts_list = list(hosts.values())
        total_hosts = len(hosts_list)

        # 按设备分组（device_group）进行分组
        groups: dict[str, list] = {}
        for host in hosts_list:
            group_name = host.data.get("device_group", "default") if host.data else "default"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(host)

        tasks: list[asyncio.Task] = []

        if len(groups) == 1 and total_hosts <= GROUP_BATCH_SIZE:
            # 单分组且设备数量少：一次性创建所有任务
            tasks = [asyncio.create_task(_execute_host(host)) for host in hosts_list]
        else:
            # 按分组创建任务，大分组内部再按 100 台分批
            celery_details_logger.info(
                "按设备分组创建任务",
                total_hosts=total_hosts,
                groups=list(groups.keys()),
                group_counts={k: len(v) for k, v in groups.items()},
            )

            for group_name, group_hosts in groups.items():
                group_size = len(group_hosts)

                if group_size <= GROUP_BATCH_SIZE:
                    # 分组内设备数量少：一次性创建该分组的任务
                    group_tasks = [asyncio.create_task(_execute_host(host)) for host in group_hosts]
                    tasks.extend(group_tasks)
                    celery_details_logger.debug(
                        "创建分组任务",
                        group=group_name,
                        count=group_size,
                    )
                else:
                    # 分组内设备数量多：按 100 台分批创建
                    celery_details_logger.info(
                        "大分组分批创建任务",
                        group=group_name,
                        total=group_size,
                        batch_size=GROUP_BATCH_SIZE,
                    )
                    for i in range(0, group_size, GROUP_BATCH_SIZE):
                        batch = group_hosts[i : i + GROUP_BATCH_SIZE]
                        batch_tasks = [asyncio.create_task(_execute_host(host)) for host in batch]
                        tasks.extend(batch_tasks)
                        # 让出事件循环，避免阻塞
                        await asyncio.sleep(0)

                # 每个分组创建完后让出事件循环
                await asyncio.sleep(0)

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
                    celery_details_logger.warning("进度回调失败", host=host_name, error=str(e), exc_info=True)

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
    celery_task_id: str | None = None,
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
        celery_task_id=celery_task_id,
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

    Raises:
        RuntimeError: 当前存在运行中的事件循环
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

    继承 AsyncRunner，默认启用重试（max_retries=2）和指数退避。

    Attributes:
        semaphore_limit: 最大并发连接数（继承自 AsyncRunner）
        max_retries: 失败重试次数（默认 2）
        retry_delay: 重试间隔（秒）
        max_retry_delay: 最大重试间隔（秒）
        exponential_backoff: 是否启用指数退避（默认 True）
    """

    def __init__(
        self,
        num_workers: int | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        max_retry_delay: float = 30.0,
        exponential_backoff: bool = True,
    ):
        """
        初始化带重试的异步运行器。

        Args:
            num_workers: 最大并发数
            max_retries: 最大重试次数（默认 2）
            retry_delay: 初始重试间隔秒数（默认 1.0）
            max_retry_delay: 最大重试间隔秒数（默认 30.0）
            exponential_backoff: 是否启用指数退避（默认 True）
        """
        super().__init__(
            num_workers,
            max_retries=max_retries,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
            exponential_backoff=exponential_backoff,
        )
