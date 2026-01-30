"""
@Author: li
@Email: lij
@FileName: minio_client.py
@DateTime: 2026-01-09 21:45:00
@Docs: MinIO 客户端封装（用于大配置备份存储）。

支持熔断器保护，当 MinIO 不可用时快速降级。
"""


import asyncio
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.circuit_breaker import CircuitBreakerOpenError, minio_circuit_breaker
from app.core.config import settings
from app.core.logger import logger


def _get_minio() -> Minio:
    """创建 MinIO 客户端实例。

    Returns:
        Minio: MinIO 客户端对象。
    """
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket_sync(client: Minio) -> None:
    """确保存储桶存在（同步版本）。

    Args:
        client (Minio): MinIO 客户端对象。

    Returns:
        None: 无返回值。
    """
    bucket = settings.MINIO_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


async def ensure_bucket() -> None:
    """确保存储桶存在（异步版本）。

    Returns:
        None: 无返回值。
    """
    client = _get_minio()
    await asyncio.to_thread(_ensure_bucket_sync, client)


async def put_text(object_name: str, content: str, *, content_type: str = "text/plain; charset=utf-8") -> None:
    """写入文本内容到 MinIO（无熔断保护）。

    Args:
        object_name (str): 对象名称。
        content (str): 文本内容。
        content_type (str): 内容类型，默认为 "text/plain; charset=utf-8"。

    Returns:
        None: 无返回值。

    Raises:
        S3Error: MinIO 操作失败时。
    """
    client = _get_minio()
    await ensure_bucket()
    data = content.encode("utf-8")
    bio = BytesIO(data)

    def _put() -> None:
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            bio,
            length=len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_put)


async def put_text_safe(
    object_name: str,
    content: str,
    *,
    content_type: str = "text/plain; charset=utf-8",
) -> bool:
    """
    写入文本内容到 MinIO（带熔断保护）。

    当 MinIO 不可用时，返回 False 而不是抛出异常。

    Args:
        object_name: 对象名称
        content: 文本内容
        content_type: 内容类型

    Returns:
        bool: 是否成功
    """
    try:
        await minio_circuit_breaker.call(
            put_text,
            object_name,
            content,
            content_type=content_type,
        )
        return True
    except CircuitBreakerOpenError as e:
        logger.warning(
            "MinIO 熔断器打开，跳过写入",
            object_name=object_name,
            remaining=e.remaining_time,
        )
        return False
    except Exception as e:
        logger.error("MinIO 写入失败", object_name=object_name, error=str(e))
        return False


async def get_text(object_name: str) -> str:
    """从 MinIO 读取文本内容（无熔断保护）。

    Args:
        object_name (str): 对象名称。

    Returns:
        str: 文本内容。

    Raises:
        S3Error: MinIO 操作失败时。
    """
    client = _get_minio()
    await ensure_bucket()

    def _get() -> str:
        resp = client.get_object(settings.MINIO_BUCKET, object_name)
        try:
            return resp.read().decode("utf-8", errors="replace")
        finally:
            resp.close()
            resp.release_conn()

    return await asyncio.to_thread(_get)


async def get_text_safe(object_name: str) -> str | None:
    """
    从 MinIO 读取文本内容（带熔断保护）。

    当 MinIO 不可用时，返回 None 而不是抛出异常。

    Args:
        object_name: 对象名称

    Returns:
        str | None: 文本内容，失败时返回 None
    """
    try:
        return await minio_circuit_breaker.call(get_text, object_name)
    except CircuitBreakerOpenError as e:
        logger.warning(
            "MinIO 熔断器打开，跳过读取",
            object_name=object_name,
            remaining=e.remaining_time,
        )
        return None
    except Exception as e:
        logger.error("MinIO 读取失败", object_name=object_name, error=str(e))
        return None


async def delete_object(object_name: str) -> None:
    """从 MinIO 删除对象（无熔断保护）。

    Args:
        object_name (str): 对象名称。

    Returns:
        None: 无返回值。

    Raises:
        S3Error: MinIO 操作失败时。
    """
    client = _get_minio()
    await ensure_bucket()

    def _del() -> None:
        try:
            client.remove_object(settings.MINIO_BUCKET, object_name)
        except S3Error as e:
            logger.warning("MinIO 删除对象失败", object_name=object_name, error=str(e))

    await asyncio.to_thread(_del)


async def delete_object_safe(object_name: str) -> bool:
    """
    从 MinIO 删除对象（带熔断保护）。

    当 MinIO 不可用时，返回 False 而不是抛出异常。

    Args:
        object_name: 对象名称

    Returns:
        bool: 是否成功
    """
    try:
        await minio_circuit_breaker.call(delete_object, object_name)
        return True
    except CircuitBreakerOpenError as e:
        logger.warning(
            "MinIO 熔断器打开，跳过删除",
            object_name=object_name,
            remaining=e.remaining_time,
        )
        return False
    except Exception as e:
        logger.error("MinIO 删除失败", object_name=object_name, error=str(e))
        return False


def get_circuit_breaker_stats() -> dict:
    """获取 MinIO 熔断器统计信息。"""
    return minio_circuit_breaker.stats()
