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
    def __init__(
        self,
        db: AsyncSession,
        *,
        redis_client: Any | None = None,
        base_dir: str | None = None,
        max_upload_mb: int | None = None,
        lock_ttl_seconds: int = 300,
    ):
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
        return await self._svc.export_table(fmt=fmt, filename_prefix="devices", df_fn=export_devices_df)

    async def build_device_import_template(self) -> ExportResult:
        return await self._svc.build_template(
            filename_prefix="device_import_template", builder=build_device_import_template
        )

    async def upload_parse_validate_device_import(
        self,
        *,
        file: UploadFile,
        allow_overwrite: bool = False,
    ) -> ImportValidateResponse:
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
        return await self._svc.preview(
            import_id=import_id,
            checksum=checksum,
            page=page,
            page_size=page_size,
            kind=kind,
        )

    async def commit_device_import(self, *, body: ImportCommitRequest) -> ImportCommitResponse:
        return await self._svc.commit(body=body, persist_fn=persist_devices, lock_namespace="import")
