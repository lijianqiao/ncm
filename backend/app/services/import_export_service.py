"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: import_export_service.py
@DateTime: 2026/01/16 08:42:34
@Docs: 导入导出服务
"""

from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache as cache_module
from app.core.config import settings
from app.features.import_export.devices import (
    DEVICE_IMPORT_COLUMN_ALIASES,
    build_device_import_template,
    export_devices_df,
    persist_devices,
    validate_devices,
)
from app.import_export import (
    ExportResult,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportValidateResponse,
)
from app.import_export import (
    ImportExportService as GenericImportExportService,
)


class ImportExportService:
    """
    导入导出服务类。

    封装通用导入导出服务，提供设备导入导出的业务接口。
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        redis_client: Any | None = None,
        base_dir: str | None = None,
        max_upload_mb: int | None = None,
        lock_ttl_seconds: int = 300,
    ):
        """
        初始化导入导出服务。

        Args:
            db: 异步数据库会话
            redis_client: Redis 客户端（可选）
            base_dir: 工作目录根路径（可选）
            max_upload_mb: 最大上传文件大小（MB，可选）
            lock_ttl_seconds: Redis 锁 TTL（秒，默认 300）
        """
        self.db = db
        resolved_base_dir = base_dir
        if resolved_base_dir is None:
            resolved_base_dir = (
                str(settings.IMPORT_EXPORT_TMP_DIR) if str(settings.IMPORT_EXPORT_TMP_DIR or "").strip() else None
            )

        self._svc = GenericImportExportService(
            db=db,
            redis_client=redis_client if redis_client is not None else cache_module.redis_client,
            base_dir=resolved_base_dir,
            max_upload_mb=int(max_upload_mb)
            if max_upload_mb is not None
            else int(settings.IMPORT_EXPORT_MAX_UPLOAD_MB),
            lock_ttl_seconds=int(lock_ttl_seconds),
        )

    async def export_devices(self, *, fmt: str) -> ExportResult:
        """
        导出设备列表。

        Args:
            fmt: 导出格式（csv 或 xlsx）

        Returns:
            ExportResult: 导出结果
        """
        return await self._svc.export_table(fmt=fmt, filename_prefix="devices", df_fn=export_devices_df)

    async def build_device_import_template(self) -> ExportResult:
        """
        生成设备导入模板文件。

        Returns:
            ExportResult: 模板文件导出结果
        """
        return await self._svc.build_template(
            filename_prefix="device_import_template", builder=build_device_import_template
        )

    async def upload_parse_validate_device_import(
        self,
        *,
        file: UploadFile,
        allow_overwrite: bool = False,
    ) -> ImportValidateResponse:
        """
        上传、解析并校验设备导入文件。

        Args:
            file: 上传的文件
            allow_overwrite: 是否允许覆盖已存在的数据

        Returns:
            ImportValidateResponse: 校验响应
        """
        return await self._svc.upload_parse_validate(
            file=file,
            column_aliases=DEVICE_IMPORT_COLUMN_ALIASES,
            validate_fn=validate_devices,
            allow_overwrite=allow_overwrite,
        )

    async def preview_device_import(
        self,
        *,
        import_id: UUID,
        checksum: str,
        page: int,
        page_size: int,
        kind: str,
    ) -> ImportPreviewResponse:
        """
        预览设备导入数据。

        Args:
            import_id: 导入任务 ID
            checksum: 文件校验和
            page: 页码（从 1 开始）
            page_size: 每页大小
            kind: 预览类型（all 或 valid）

        Returns:
            ImportPreviewResponse: 预览响应
        """
        return await self._svc.preview(
            import_id=import_id,
            checksum=checksum,
            page=page,
            page_size=page_size,
            kind=kind,
        )

    async def commit_device_import(self, *, body: ImportCommitRequest) -> ImportCommitResponse:
        """
        提交设备导入任务。

        Args:
            body: 提交请求体

        Returns:
            ImportCommitResponse: 提交响应
        """
        return await self._svc.commit(body=body, persist_fn=persist_devices, lock_namespace="import")
