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
    device_name: str | None = Field(default=None, description="设备名称")

    old_backup_id: UUID | None = Field(default=None, description="旧备份ID")
    new_backup_id: UUID | None = Field(default=None, description="新备份ID")

    # 前端字段（对齐）
    old_hash: str | None = Field(default=None, description="旧版本 Hash/MD5")
    new_hash: str | None = Field(default=None, description="新版本 Hash/MD5")
    diff_content: str | None = Field(default=None, description="unified diff 文本")
    has_changes: bool = Field(default=False, description="是否存在变更")
    created_at: datetime = Field(default_factory=datetime.now, description="对比生成时间")

    # 兼容旧字段（历史接口/内部使用）
    old_md5: str | None = Field(default=None, description="旧MD5（兼容字段）")
    new_md5: str | None = Field(default=None, description="新MD5（兼容字段）")
    diff: str = Field(default="", description="unified diff 文本（兼容字段）")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间（兼容字段）")

    message: str | None = Field(default=None, description="提示信息")
