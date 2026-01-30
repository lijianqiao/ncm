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
    """导入上传响应 Schema。

    Attributes:
        import_id (UUID): 导入 ID。
        checksum (str): 文件 SHA256 校验和。
        filename (str): 文件名。
        content_type (str | None): 文件 MIME 类型。
        size_bytes (int): 文件大小（字节）。
    """

    import_id: UUID
    checksum: str
    filename: str
    content_type: str | None = None
    size_bytes: int


class ImportErrorItem(BaseModel):
    """导入错误项 Schema。

    Attributes:
        row_number (int): 源文件行号（从 1 开始，不含表头）。
        field (str | None): 字段名（可选）。
        message (str): 错误原因。
    """

    row_number: int = Field(..., description="源文件行号（从 1 开始，不含表头）")
    field: str | None = Field(default=None, description="字段名（可选）")
    message: str = Field(..., description="错误原因")


class ImportValidateResponse(BaseModel):
    """导入验证响应 Schema。

    Attributes:
        import_id (UUID): 导入 ID。
        checksum (str): 文件 SHA256 校验和。
        total_rows (int): 总行数。
        valid_rows (int): 有效行数。
        error_rows (int): 错误行数。
        errors (list[ImportErrorItem]): 错误明细（可分页/截断返回）。
    """

    import_id: UUID
    checksum: str
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[ImportErrorItem] = Field(default_factory=list, description="错误明细（可分页/截断返回）")


class ImportPreviewRow(BaseModel):
    """导入预览行 Schema。

    Attributes:
        row_number (int): 行号。
        data (dict[str, Any]): 行数据。
    """

    row_number: int
    data: dict[str, Any]


class ImportPreviewResponse(BaseModel):
    """导入预览响应 Schema。

    Attributes:
        import_id (UUID): 导入 ID。
        checksum (str): 文件 SHA256 校验和。
        page (int): 当前页码。
        page_size (int): 每页大小。
        total_rows (int): 总行数。
        rows (list[ImportPreviewRow]): 预览行列表。
    """

    import_id: UUID
    checksum: str
    page: int
    page_size: int
    total_rows: int
    rows: list[ImportPreviewRow]


class ImportCommitRequest(BaseModel):
    """导入提交请求 Schema。

    Attributes:
        import_id (UUID): 导入 ID。
        checksum (str): 文件 SHA256 校验和。
        allow_overwrite (bool): 是否允许覆盖已存在的数据，默认 False。
    """

    import_id: UUID
    checksum: str
    allow_overwrite: bool = False


class ImportCommitResponse(BaseModel):
    """导入提交响应 Schema。

    Attributes:
        import_id (UUID): 导入 ID。
        checksum (str): 文件 SHA256 校验和。
        status (str): 导入状态。
        imported_rows (int): 成功导入的行数。
        created_at (datetime): 创建时间。
    """

    import_id: UUID
    checksum: str
    status: str
    imported_rows: int
    created_at: datetime
