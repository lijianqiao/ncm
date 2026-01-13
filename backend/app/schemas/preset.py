"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: preset.py
@DateTime: 2026-01-13 12:45:00
@Docs: 预设模板 Schema 定义。
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PresetInfo(BaseModel):
    """预设模板简要信息。"""

    id: str = Field(..., description="预设 ID")
    name: str = Field(..., description="预设名称")
    description: str = Field(default="", description="预设描述")
    category: str = Field(..., description="分类: show/config")
    supported_vendors: list[str] = Field(..., description="支持的厂商列表")


class PresetDetail(PresetInfo):
    """预设模板详情（含参数 Schema）。"""

    parameters_schema: dict[str, Any] = Field(..., description="参数 JSON Schema")


class PresetExecuteRequest(BaseModel):
    """执行预设请求体。"""

    device_id: UUID = Field(..., description="目标设备 ID")
    params: dict[str, Any] = Field(default_factory=dict, description="预设参数")


class PresetExecuteResult(BaseModel):
    """预设执行结果。"""

    success: bool = Field(..., description="执行是否成功")
    raw_output: str = Field(default="", description="原始命令输出")
    parsed_output: Any = Field(default=None, description="TextFSM 结构化解析结果")
    parse_error: str | None = Field(default=None, description="解析错误信息（如有）")
    error_message: str | None = Field(default=None, description="执行错误信息（如有）")

    # OTP 断点续传（otp_manual 模式）
    otp_required: bool = Field(default=False, description="是否需要输入 OTP")
    otp_required_groups: list[dict[str, str]] = Field(default_factory=list, description="需要 OTP 的设备分组")
    expires_in: int | None = Field(default=None, description="OTP 缓存剩余有效期（秒）")
    next_action: str | None = Field(default=None, description="建议的下一步动作")
