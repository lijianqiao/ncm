"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: permission.py
@DateTime: 2026-01-06 00:00:00
@Docs: 权限字典相关 Schema。
"""

from pydantic import BaseModel, Field


class PermissionDictItem(BaseModel):
    code: str = Field(..., description="权限码")
    name: str = Field(..., description="权限名称")
    description: str | None = Field(None, description="权限描述")
