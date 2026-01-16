"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: service.py
@DateTime: 2026/01/16
@Docs: 导入导出通用服务（FastAPI 可复用）
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import polars as pl
from fastapi import UploadFile
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.ext.asyncio import AsyncSession

from app.import_export import parse as ie_parse
from app.import_export.schemas import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorItem,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportValidateResponse,
)
from app.import_export.storage import (
    create_export_path,
    get_import_paths,
    new_import_id,
    now_ts,
    read_meta,
    sha256_file,
    write_meta,
)


class RedisLike(Protocol):
    def set(self, *args: Any, **kwargs: Any) -> Any: ...

    def delete(self, *args: Any, **kwargs: Any) -> Any: ...


ExportDfFn = Callable[[AsyncSession], Awaitable[pl.DataFrame]]
BuildTemplateFn = Callable[[Path], None]


class ValidateFn(Protocol):
    async def __call__(
        self,
        db: AsyncSession,
        df: pl.DataFrame,
        *,
        allow_overwrite: bool = False,
    ) -> tuple[pl.DataFrame, list[dict[str, Any]]]: ...


class PersistFn(Protocol):
    async def __call__(
        self,
        db: AsyncSession,
        valid_df: pl.DataFrame,
        *,
        allow_overwrite: bool = False,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ExportResult:
    path: Path
    filename: str
    media_type: str


class ImportExportService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        redis_client: RedisLike | None = None,
        max_upload_mb: int = 20,
        lock_ttl_seconds: int = 300,
    ):
        self.db = db
        self.redis_client = redis_client
        self.max_upload_mb = max_upload_mb
        self.lock_ttl_seconds = lock_ttl_seconds

    async def export_table(
        self,
        *,
        fmt: str,
        filename_prefix: str,
        df_fn: ExportDfFn,
    ) -> ExportResult:
        df = await df_fn(self.db)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{ts}.{fmt}"
        file_path = create_export_path(filename)

        if fmt == "csv":
            df.write_csv(file_path)
            return ExportResult(path=file_path, filename=filename, media_type="text/csv")

        wb = Workbook()
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook.active is None")
        ws = cast(Worksheet, ws)
        ws.title = filename_prefix

        headers = df.columns
        ws.append(headers)
        for row in df.to_dicts():
            ws.append([row.get(h, "") for h in headers])
        ws.freeze_panes = "A2"
        wb.save(file_path)

        return ExportResult(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    async def build_template(
        self,
        *,
        filename_prefix: str,
        builder: BuildTemplateFn,
    ) -> ExportResult:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{ts}.xlsx"
        file_path = create_export_path(filename)
        builder(file_path)
        return ExportResult(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    async def upload_parse_validate(
        self,
        *,
        file: UploadFile,
        column_aliases: dict[str, str],
        validate_fn: ValidateFn,
        allow_overwrite: bool = False,
    ) -> ImportValidateResponse:
        import_id = new_import_id()
        paths = get_import_paths(import_id)
        paths.root.mkdir(parents=True, exist_ok=True)

        filename = file.filename or "upload"
        content_type = file.content_type
        ext = Path(filename).suffix.lower()
        original_path = paths.original.with_suffix(ext)

        size = 0
        with original_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > int(self.max_upload_mb) * 1024 * 1024:
                    raise ValueError("上传文件过大")
                out.write(chunk)

        checksum = sha256_file(original_path)
        meta: dict[str, Any] = {
            "import_id": str(import_id),
            "filename": filename,
            "content_type": content_type,
            "checksum": checksum,
            "size_bytes": size,
            "created_at": now_ts(),
            "status": "uploaded",
        }
        write_meta(paths, meta)

        parsed = ie_parse.parse_tabular_file(original_path, filename=filename)
        df = ie_parse.normalize_columns(parsed.df, column_aliases)
        df.write_parquet(paths.parsed_parquet)

        valid_df, errors = await validate_fn(self.db, df, allow_overwrite=allow_overwrite)
        paths.errors_json.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        if not valid_df.is_empty():
            valid_df.write_parquet(paths.valid_parquet)

        resp = ImportValidateResponse(
            import_id=import_id,
            checksum=checksum,
            total_rows=int(parsed.total_rows),
            valid_rows=int(valid_df.height) if not valid_df.is_empty() else 0,
            error_rows=len({e["row_number"] for e in errors if int(e.get("row_number") or 0) > 0}) if errors else 0,
            errors=[
                ImportErrorItem(
                    row_number=int(e.get("row_number") or 0),
                    field=cast(str | None, e.get("field")),
                    message=str(e.get("message") or ""),
                )
                for e in errors[:200]
            ],
        )

        meta["status"] = "validated"
        meta["total_rows"] = resp.total_rows
        meta["valid_rows"] = resp.valid_rows
        meta["error_rows"] = resp.error_rows
        write_meta(paths, meta)
        return resp

    async def preview(
        self,
        *,
        import_id: UUID,
        checksum: str,
        page: int,
        page_size: int,
        kind: str,
    ) -> ImportPreviewResponse:
        paths = get_import_paths(import_id)
        meta = read_meta(paths)
        if str(meta.get("checksum")) != checksum:
            raise ValueError("checksum 不匹配")

        parquet = paths.valid_parquet if kind == "valid" else paths.parsed_parquet
        if not parquet.exists():
            return ImportPreviewResponse(
                import_id=import_id,
                checksum=checksum,
                page=page,
                page_size=page_size,
                total_rows=0,
                rows=[],
            )

        df = pl.scan_parquet(parquet).slice((page - 1) * page_size, page_size).collect()
        total_rows = int(pl.scan_parquet(parquet).select(pl.len()).collect()[0, 0])
        rows: list[ImportPreviewRow] = []
        for r in df.to_dicts():
            row_number = int(r.get("row_number") or 0)
            data = {k: v for k, v in r.items() if k != "row_number"}
            rows.append(ImportPreviewRow(row_number=row_number, data=data))

        return ImportPreviewResponse(
            import_id=import_id,
            checksum=checksum,
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            rows=rows,
        )

    async def commit(
        self,
        *,
        body: ImportCommitRequest,
        persist_fn: PersistFn,
        lock_namespace: str = "import",
    ) -> ImportCommitResponse:
        paths = get_import_paths(body.import_id)
        meta = read_meta(paths)
        if str(meta.get("checksum")) != body.checksum:
            raise ValueError("checksum 不匹配")

        if meta.get("status") == "committed":
            committed_at = int(meta.get("committed_at") or now_ts())
            return ImportCommitResponse(
                import_id=body.import_id,
                checksum=body.checksum,
                status="committed",
                imported_rows=int(meta.get("imported_rows") or 0),
                created_at=datetime.fromtimestamp(committed_at),
            )

        if paths.errors_json.exists():
            errors = json.loads(paths.errors_json.read_text(encoding="utf-8"))
            if errors:
                raise ValueError("存在校验错误，整批不可导入")

        lock_key = f"{lock_namespace}:lock:{body.import_id}"
        lock_acquired = False
        if self.redis_client is not None:
            lock_acquired = bool(await self.redis_client.set(lock_key, "1", ex=self.lock_ttl_seconds, nx=True))
            if not lock_acquired:
                raise ValueError("导入正在执行，请稍后重试")

        valid_df = pl.read_parquet(paths.valid_parquet) if paths.valid_parquet.exists() else pl.DataFrame()
        try:
            await self.db.rollback()
        except Exception:
            pass

        imported_rows = await persist_fn(self.db, valid_df, allow_overwrite=body.allow_overwrite)

        meta["status"] = "committed"
        meta["committed_at"] = now_ts()
        meta["imported_rows"] = imported_rows
        write_meta(paths, meta)

        if self.redis_client is not None and lock_acquired:
            try:
                await self.redis_client.delete(lock_key)
            except Exception:
                pass

        return ImportCommitResponse(
            import_id=body.import_id,
            checksum=body.checksum,
            status="committed",
            imported_rows=imported_rows,
            created_at=datetime.fromtimestamp(int(meta.get("committed_at") or now_ts())),
        )
