"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: circuit_breaker.py
@DateTime: 2026-01-28 10:00:00
@Docs: 熔断器实现，用于保护外部服务调用（如 MinIO）。

支持三种状态：
- CLOSED: 正常工作，请求通过
- OPEN: 熔断状态，请求快速失败
- HALF_OPEN: 半开状态，尝试恢复
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.enums import CircuitState
from app.core.logger import logger


class CircuitBreakerOpenError(Exception):
    """熔断器打开时抛出的异常。"""

    def __init__(self, name: str, remaining_time: float):
        """初始化熔断器打开异常。

        Args:
            name (str): 熔断器名称。
            remaining_time (float): 剩余恢复时间（秒）。
        """
        self.name = name
        self.remaining_time = remaining_time
        super().__init__(f"熔断器 '{name}' 已打开，剩余 {remaining_time:.1f}s 后尝试恢复")


@dataclass
class CircuitBreaker:
    """
    熔断器实现。

    当失败次数达到阈值时，熔断器将打开，阻止后续请求。
    经过恢复超时后，熔断器进入半开状态，尝试恢复。
    如果半开状态下请求成功，则关闭熔断器；如果失败，则重新打开。

    Attributes:
        name: 熔断器名称（用于日志）
        failure_threshold: 失败阈值，达到后打开熔断器
        recovery_timeout: 恢复超时秒数，经过后尝试恢复
        success_threshold: 半开状态下连续成功次数阈值
    """

    name: str = "default"
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2

    # 内部状态
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """获取当前状态（自动检测状态转换）。

        Returns:
            CircuitState: 当前熔断器状态。
        """
        if self._state == CircuitState.OPEN:
            # 检查是否应该转入半开状态
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        """熔断器是否打开（阻止请求）。

        Returns:
            bool: 如果熔断器处于打开状态则返回 True。
        """
        return self.state == CircuitState.OPEN

    def _remaining_time(self) -> float:
        """计算熔断器剩余打开时间。

        Returns:
            float: 剩余打开时间（秒），如果未打开则返回 0.0。
        """
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self.recovery_timeout - elapsed)

    async def _record_success(self) -> None:
        """记录成功请求。

        更新失败计数和状态：
        - 如果处于半开状态，增加成功计数，达到阈值后关闭熔断器
        - 否则重置失败计数并关闭熔断器

        Returns:
            None: 无返回值。
        """
        async with self._lock:
            self._failures = 0
            if self._state == CircuitState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._successes = 0
                    logger.info("熔断器恢复正常", name=self.name)
            else:
                self._state = CircuitState.CLOSED

    async def _record_failure(self) -> None:
        """记录失败请求。

        更新失败计数和状态：
        - 如果处于半开状态，重新打开熔断器
        - 如果失败次数达到阈值，打开熔断器

        Returns:
            None: 无返回值。
        """
        async with self._lock:
            self._failures += 1
            self._successes = 0
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，重新打开
                self._state = CircuitState.OPEN
                logger.warning(
                    "熔断器半开状态失败，重新打开",
                    name=self.name,
                    recovery_timeout=self.recovery_timeout,
                )
            elif self._failures >= self.failure_threshold:
                # 达到失败阈值，打开熔断器
                self._state = CircuitState.OPEN
                logger.warning(
                    "熔断器打开",
                    name=self.name,
                    failures=self._failures,
                    threshold=self.failure_threshold,
                    recovery_timeout=self.recovery_timeout,
                )

    async def call[T](
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        通过熔断器调用异步函数。

        Args:
            func: 要调用的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开时
            Exception: 函数执行异常
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            remaining = self._remaining_time()
            logger.debug("熔断器阻止请求", name=self.name, remaining=remaining)
            raise CircuitBreakerOpenError(self.name, remaining)

        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            raise e from None

    def stats(self) -> dict[str, Any]:
        """获取熔断器统计信息。

        Returns:
            dict[str, Any]: 包含熔断器状态、失败次数、成功次数等信息的字典。
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failures,
            "successes": self._successes,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "remaining_time": self._remaining_time() if self._state == CircuitState.OPEN else 0.0,
        }


# ===== 全局熔断器实例 =====

# MinIO 熔断器（用于配置备份存储）
minio_circuit_breaker = CircuitBreaker(
    name="MinIO",
    failure_threshold=getattr(settings, "MINIO_CIRCUIT_FAILURE_THRESHOLD", 5),
    recovery_timeout=getattr(settings, "MINIO_CIRCUIT_RECOVERY_TIMEOUT", 60.0),
    success_threshold=getattr(settings, "MINIO_CIRCUIT_SUCCESS_THRESHOLD", 2),
)
