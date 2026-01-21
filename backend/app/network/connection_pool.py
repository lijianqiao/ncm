"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: connection_pool.py
@DateTime: 2026-01-21 10:00:00
@Docs: Scrapli 异步连接池管理器。

提供连接复用能力，减少频繁连接同一设备的开销。
特性：
- 基于 (host, port, username) 的连接缓存
- 自动连接健康检查
- 可配置的连接超时和最大空闲时间
- 异步安全（使用 asyncio.Lock）
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from scrapli import AsyncScrapli

from app.core.config import settings
from app.core.logger import logger


@dataclass
class PooledConnection:
    """连接池中的连接包装。"""

    conn: AsyncScrapli
    host: str
    port: int
    username: str
    platform: str
    created_at: float = field(default_factory=time.monotonic)
    last_used_at: float = field(default_factory=time.monotonic)
    use_count: int = 0

    @property
    def age(self) -> float:
        """连接存活时间（秒）。"""
        return time.monotonic() - self.created_at

    @property
    def idle_time(self) -> float:
        """连接空闲时间（秒）。"""
        return time.monotonic() - self.last_used_at

    def touch(self) -> None:
        """更新最后使用时间。"""
        self.last_used_at = time.monotonic()
        self.use_count += 1


class AsyncConnectionPool:
    """
    Scrapli 异步连接池。

    使用示例：
        ```python
        pool = AsyncConnectionPool()

        # 获取连接（自动复用或创建新连接）
        async with pool.acquire(host="192.168.1.1", ...) as conn:
            response = await conn.send_command("show version")

        # 关闭连接池
        await pool.close()
        ```

    Attributes:
        max_connections: 最大连接数
        max_idle_time: 最大空闲时间（秒），超过后连接将被关闭
        max_age: 连接最大存活时间（秒），超过后强制重建
        health_check: 是否在获取连接时进行健康检查
    """

    def __init__(
        self,
        max_connections: int | None = None,
        max_idle_time: float | None = None,
        max_age: float | None = None,
        health_check: bool = True,
    ):
        """
        初始化连接池。

        Args:
            max_connections: 最大连接数（默认从配置读取 SCRAPLI_POOL_MAX_CONNECTIONS）
            max_idle_time: 最大空闲时间秒数（默认从配置读取 SCRAPLI_POOL_MAX_IDLE_TIME）
            max_age: 连接最大存活时间秒数（默认从配置读取 SCRAPLI_POOL_MAX_AGE）
            health_check: 是否在复用连接前进行健康检查（默认 True）
        """
        self.max_connections = max_connections or settings.SCRAPLI_POOL_MAX_CONNECTIONS
        self.max_idle_time = max_idle_time or float(settings.SCRAPLI_POOL_MAX_IDLE_TIME)
        self.max_age = max_age or float(settings.SCRAPLI_POOL_MAX_AGE)
        self.health_check = health_check

        self._pool: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    def _make_key(self, host: str, port: int, username: str) -> str:
        """生成连接缓存键。"""
        return f"{host}:{port}:{username}"

    async def _is_connection_healthy(self, pooled: PooledConnection) -> bool:
        """检查连接是否健康。"""
        if pooled.age > self.max_age:
            logger.debug("连接超过最大存活时间", host=pooled.host, age=pooled.age, max_age=self.max_age)
            return False

        if pooled.idle_time > self.max_idle_time:
            logger.debug("连接空闲时间过长", host=pooled.host, idle=pooled.idle_time, max_idle=self.max_idle_time)
            return False

        if self.health_check:
            try:
                # 尝试获取提示符来验证连接
                await pooled.conn.get_prompt()
                return True
            except Exception as e:
                logger.debug("连接健康检查失败", host=pooled.host, error=str(e))
                return False

        return True

    async def _close_connection(self, pooled: PooledConnection) -> None:
        """安全关闭连接。"""
        try:
            await pooled.conn.close()
            logger.debug(
                "连接池关闭连接",
                host=pooled.host,
                port=pooled.port,
                use_count=pooled.use_count,
                age=int(pooled.age),
            )
        except Exception as e:
            logger.debug("关闭连接失败", host=pooled.host, error=str(e))

    async def acquire(
        self,
        host: str,
        username: str,
        password: str,
        platform: str,
        port: int = 22,
        **kwargs: Any,
    ) -> "PooledConnectionContext":
        """
        获取连接（优先复用，无可用连接时创建新连接）。

        Args:
            host: 设备 IP 地址或主机名
            username: SSH 用户名
            password: SSH 密码
            platform: Scrapli 平台标识
            port: SSH 端口
            **kwargs: 其他 Scrapli 参数

        Returns:
            PooledConnectionContext: 连接上下文管理器

        Raises:
            RuntimeError: 连接池已关闭
        """
        if self._closed:
            raise RuntimeError("连接池已关闭")

        key = self._make_key(host, port, username)

        async with self._lock:
            # 尝试复用现有连接
            if key in self._pool:
                pooled = self._pool[key]
                if await self._is_connection_healthy(pooled):
                    pooled.touch()
                    logger.debug(
                        "连接池复用连接",
                        host=host,
                        port=port,
                        use_count=pooled.use_count,
                        idle_time=int(pooled.idle_time),
                    )
                    return PooledConnectionContext(self, pooled, key, reused=True)
                else:
                    # 连接不健康，关闭并移除
                    await self._close_connection(pooled)
                    del self._pool[key]

            # 检查连接数限制
            if len(self._pool) >= self.max_connections:
                # 移除最旧的空闲连接
                await self._evict_oldest()

            # 创建新连接（AsyncScrapli 必须使用异步 transport）
            conn_kwargs = {
                "host": host,
                "auth_username": username,
                "auth_password": password,
                "port": port,
                "platform": platform,
                "transport": "asyncssh",  # AsyncScrapli 需要异步 transport
                **kwargs,
            }
            conn = AsyncScrapli(**conn_kwargs)
            await conn.open()

            pooled = PooledConnection(
                conn=conn,
                host=host,
                port=port,
                username=username,
                platform=platform,
            )
            pooled.touch()
            self._pool[key] = pooled

            logger.debug(
                "连接池创建新连接",
                host=host,
                port=port,
                platform=platform,
                pool_size=len(self._pool),
            )

            return PooledConnectionContext(self, pooled, key, reused=False)

    async def _evict_oldest(self) -> None:
        """移除最旧的空闲连接。"""
        if not self._pool:
            return

        # 按空闲时间排序，移除最久未使用的
        oldest_key = max(self._pool.keys(), key=lambda k: self._pool[k].idle_time)
        oldest = self._pool.pop(oldest_key)
        await self._close_connection(oldest)
        logger.debug("连接池淘汰最旧连接", host=oldest.host, idle_time=int(oldest.idle_time))

    async def release(self, key: str, pooled: PooledConnection, *, discard: bool = False) -> None:
        """
        释放连接回连接池。

        Args:
            key: 连接缓存键
            pooled: 连接包装对象
            discard: 是否丢弃连接（不放回池中）
        """
        async with self._lock:
            if discard or self._closed:
                await self._close_connection(pooled)
                if key in self._pool:
                    del self._pool[key]
            else:
                pooled.touch()

    async def close(self) -> None:
        """关闭连接池，释放所有连接。"""
        async with self._lock:
            self._closed = True
            for _, pooled in list(self._pool.items()):
                await self._close_connection(pooled)
            self._pool.clear()
            logger.info("连接池已关闭")

    async def cleanup_idle(self) -> int:
        """
        清理空闲连接。

        Returns:
            int: 清理的连接数
        """
        cleaned = 0
        async with self._lock:
            for key in list(self._pool.keys()):
                pooled = self._pool[key]
                if pooled.idle_time > self.max_idle_time or pooled.age > self.max_age:
                    await self._close_connection(pooled)
                    del self._pool[key]
                    cleaned += 1

        if cleaned > 0:
            logger.info("连接池清理空闲连接", cleaned=cleaned, remaining=len(self._pool))

        return cleaned

    @property
    def size(self) -> int:
        """当前连接池大小。"""
        return len(self._pool)

    def stats(self) -> dict[str, Any]:
        """获取连接池统计信息。"""
        return {
            "size": len(self._pool),
            "max_connections": self.max_connections,
            "closed": self._closed,
            "connections": [
                {
                    "host": p.host,
                    "port": p.port,
                    "platform": p.platform,
                    "use_count": p.use_count,
                    "age": int(p.age),
                    "idle_time": int(p.idle_time),
                }
                for p in self._pool.values()
            ],
        }


class PooledConnectionContext:
    """连接池连接的上下文管理器。"""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        pooled: PooledConnection,
        key: str,
        reused: bool = False,
    ):
        self._pool = pool
        self._pooled = pooled
        self._key = key
        self._reused = reused
        self._discard = False

    @property
    def conn(self) -> AsyncScrapli:
        """获取底层 AsyncScrapli 连接。"""
        return self._pooled.conn

    @property
    def reused(self) -> bool:
        """是否为复用的连接。"""
        return self._reused

    def discard(self) -> None:
        """标记连接为需要丢弃（不放回池中）。"""
        self._discard = True

    async def __aenter__(self) -> AsyncScrapli:
        return self._pooled.conn

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 如果发生异常，丢弃连接
        if exc_type is not None:
            self._discard = True
        await self._pool.release(self._key, self._pooled, discard=self._discard)


# ===== 全局连接池实例（懒加载）=====
_global_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_connection_pool() -> AsyncConnectionPool:
    """
    获取全局连接池实例（懒加载）。

    Returns:
        AsyncConnectionPool: 连接池实例
    """
    global _global_pool

    if _global_pool is not None and not _global_pool._closed:
        return _global_pool

    async with _pool_lock:
        if _global_pool is None or _global_pool._closed:
            _global_pool = AsyncConnectionPool(
                max_connections=getattr(settings, "SCRAPLI_POOL_MAX_CONNECTIONS", 100),
                max_idle_time=getattr(settings, "SCRAPLI_POOL_MAX_IDLE_TIME", 300.0),
                max_age=getattr(settings, "SCRAPLI_POOL_MAX_AGE", 3600.0),
                health_check=getattr(settings, "SCRAPLI_POOL_HEALTH_CHECK", True),
            )
            logger.info(
                "全局连接池已初始化",
                max_connections=_global_pool.max_connections,
                max_idle_time=_global_pool.max_idle_time,
            )

    return _global_pool


async def close_connection_pool() -> None:
    """关闭全局连接池。"""
    global _global_pool

    if _global_pool is not None:
        await _global_pool.close()
        _global_pool = None
