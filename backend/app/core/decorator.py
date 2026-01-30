"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: decorator.py
@DateTime: 2025-12-30 14:50:00
@Docs: 数据库事务与重试装饰器 (Database Transaction & Retry Decorators).
"""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

RT = TypeVar("RT")


def with_db_retry(max_retries: int = 3, initial_delay: float = 0.1) -> Callable:
    """数据库操作重试装饰器。

    处理 SQLAlchemy 操作性错误（如连接断开、死锁）。

    Args:
        max_retries (int): 最大重试次数，默认为 3。
        initial_delay (float): 初始延迟秒数（指数退避），默认为 0.1。

    Returns:
        Callable: 装饰器函数。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except SQLAlchemyError as e:
                    # 可以在这里添加具体的错误码判断，例如 PG 的 40001 (Serialization failure)
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"数据库操作失败，已重试 {max_retries} 次: {e}")
                        raise

                    import asyncio

                    delay = initial_delay * (2 ** (retries - 1))
                    logger.warning(f"数据库错误 {e}，{delay}秒后重试 ({retries}/{max_retries})...")
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


def transactional() -> Callable:
    """事务管理装饰器。

    自动管理事务提交和回滚：
    1. 成功执行后自动 commit。
    2. 抛出异常时自动 rollback。

    要求：
    被装饰的函数必须包含一个名为 'self' 的参数（用于类方法），
    且该实例必须有一个名为 'db' 的属性，是 AsyncSession 类型。
    或者，被装饰函数直接包含名为 'db' 的 AsyncSession 参数。

    Returns:
        Callable: 装饰器函数。

    Usage:
        @transactional()
        async def create_user(self, user_in):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            def is_db_session(obj: Any) -> bool:
                return obj is not None and hasattr(obj, "commit") and hasattr(obj, "rollback")

            db_session: Any | None = None

            # 1) 优先从 kwargs['db'] 获取
            if "db" in kwargs and is_db_session(kwargs.get("db")):
                db_session = kwargs.get("db")

            # 2) 尝试从 self.db 获取 (针对 Service 类方法)
            if db_session is None and args:
                self_obj = args[0]
                if hasattr(self_obj, "db") and is_db_session(self_obj.db):
                    db_session = self_obj.db

            # 3) 通过函数签名绑定参数，支持位置参数传入 db
            if db_session is None:
                try:
                    bound = inspect.signature(func).bind_partial(*args, **kwargs)
                except TypeError:
                    bound = None

                if bound is not None:
                    if is_db_session(bound.arguments.get("db")):
                        db_session = bound.arguments.get("db")
                    else:
                        for v in bound.arguments.values():
                            if is_db_session(v):
                                db_session = v
                                break

            if db_session is None:
                raise RuntimeError(f"@transactional used on {func.__name__} but no 'db' session found.")

            try:
                result = await func(*args, **kwargs)
                # 成功执行，提交事务
                await db_session.commit()

                # 可选：提交后任务（例如缓存失效）
                if args:
                    self_obj = args[0]
                    post_commit_tasks = getattr(self_obj, "_post_commit_tasks", None)
                    if isinstance(post_commit_tasks, list) and post_commit_tasks:
                        for task in post_commit_tasks:
                            try:
                                await task()
                            except Exception as e:
                                logger.warning(f"post_commit 任务执行失败: {e}")
                        self_obj._post_commit_tasks = []

                return result
            except Exception as e:
                # 发生异常，回滚事务
                logger.error(f"{func.__name__} 中的事务回滚: {e}")
                await db_session.rollback()
                raise

        return wrapper

    return decorator
