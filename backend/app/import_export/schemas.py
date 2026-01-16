"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: schemas.py
@DateTime: 2026/01/16 08:44:23
@Docs: 导入导出数据模型
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportUploadResponse(BaseModel):
    import_id: UUID
    checksum: str
    filename: str
    content_type: str | None = None
    size_bytes: int


class ImportErrorItem(BaseModel):
    row_number: int = Field(..., description="源文件行号（从 1 开始，不含表头）")
    field: str | None = Field(default=None, description="字段名（可选）")
    message: str = Field(..., description="错误原因")


class ImportValidateResponse(BaseModel):
    import_id: UUID
    checksum: str
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[ImportErrorItem] = Field(default_factory=list, description="错误明细（可分页/截断返回）")


class ImportPreviewRow(BaseModel):
    row_number: int
    data: dict[str, Any]


class ImportPreviewResponse(BaseModel):
    import_id: UUID
    checksum: str
    page: int
    page_size: int
    total_rows: int
    rows: list[ImportPreviewRow]


class ImportCommitRequest(BaseModel):
    import_id: UUID
    checksum: str
    allow_overwrite: bool = False


class ImportCommitResponse(BaseModel):
    import_id: UUID
    checksum: str
    status: str
    imported_rows: int
    created_at: datetime
