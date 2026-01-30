"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: db.py
@DateTime: 2025-12-30 11:40:00
@Docs: Database connection and session management.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,
    future=True,
    pool_pre_ping=True,  # 连接前检测连接是否有效
    pool_size=settings.DB_POOL_SIZE,  # 连接池大小
    max_overflow=settings.DB_MAX_OVERFLOW,  # 最大溢出连接数
    pool_recycle=settings.DB_POOL_RECYCLE,  # 连接回收时间，防止长时间空闲连接超时
    pool_timeout=settings.DB_POOL_TIMEOUT,  # 获取连接超时时间
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def close_db() -> None:
    """关闭数据库引擎连接池，在应用关闭时调用。

    Returns:
        None: 无返回值。
    """
    await engine.dispose()
