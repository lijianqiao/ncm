"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: common.py
@DateTime: 2025-12-30 15:35:00
@Docs: 通用 Schema 定义 (Common Schemas).
"""

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class TimestampSchema(BaseModel):
    """
    时间戳混入 Schema。
    """

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class ResponseBase[T](BaseModel):
    """
    统一响应格式。
    """

    code: int = 200
    message: str = "Success"
    data: T | None = None


class PaginatedResponse[T](BaseModel):
    """
    分页响应格式。
    """

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    items: list[T] = Field(default_factory=list, description="数据列表")


class BatchDeleteRequest(BaseModel):
    """
    批量删除请求。
    """

    ids: list[UUID] = Field(..., description="要删除的 ID 列表")
    hard_delete: bool = Field(False, description="是否硬删除 (默认软删除)")


class BatchRestoreRequest(BaseModel):
    """
    批量恢复请求。

    用于从回收站批量恢复软删除数据。
    """

    ids: list[UUID] = Field(..., description="要恢复的 ID 列表")


class BatchOperationResult(BaseModel):
    """
    批量操作结果。
    """

    success_count: int = Field(..., description="成功数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="失败的 ID 列表")
    message: str = Field("操作完成", description="操作结果消息")
