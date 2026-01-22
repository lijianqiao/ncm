"""
@Author: li
@Email: lij
@FileName: minio_client.py
@DateTime: 2026-01-09 21:45:00
@Docs: MinIO 客户端封装（用于大配置备份存储）。
"""


import asyncio
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logger import logger


def _get_minio() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket_sync(client: Minio) -> None:
    bucket = settings.MINIO_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


async def ensure_bucket() -> None:
    client = _get_minio()
    await asyncio.to_thread(_ensure_bucket_sync, client)


async def put_text(object_name: str, content: str, *, content_type: str = "text/plain; charset=utf-8") -> None:
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


async def get_text(object_name: str) -> str:
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


async def delete_object(object_name: str) -> None:
    client = _get_minio()
    await ensure_bucket()

    def _del() -> None:
        try:
            client.remove_object(settings.MINIO_BUCKET, object_name)
        except S3Error as e:
            logger.warning("MinIO 删除对象失败", object_name=object_name, error=str(e))

    await asyncio.to_thread(_del)
