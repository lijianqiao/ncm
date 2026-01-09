"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: diff.py
@DateTime: 2026-01-10 03:35:00
@Docs: 配置差异 Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DiffResponse(BaseModel):
    """差异响应（unified diff）。"""

    device_id: UUID = Field(..., description="设备ID")
    old_backup_id: UUID | None = Field(default=None, description="旧备份ID")
    new_backup_id: UUID | None = Field(default=None, description="新备份ID")
    old_md5: str | None = Field(default=None, description="旧MD5")
    new_md5: str | None = Field(default=None, description="新MD5")
    diff: str = Field(default="", description="unified diff 文本")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    message: str | None = Field(default=None, description="提示信息")

