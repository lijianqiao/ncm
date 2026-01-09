"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: inventory_audit.py
@DateTime: 2026-01-09 21:15:00
@Docs: 资产盘点任务 Schema。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import InventoryAuditStatus


class InventoryAuditScope(BaseModel):
    """盘点范围（强类型）。"""

    subnets: list[str] | None = Field(
        default=None,
        description="要扫描的网段列表(CIDR)，例如 192.168.1.0/24",
        json_schema_extra={
            "examples": [["192.168.1.0/24", "10.0.0.0/24"]],
        },
    )
    dept_id: UUID | None = Field(
        default=None,
        description="部门ID（可选）。若提供，将纳入该部门下 CMDB 设备的 IP 作为扫描目标",
        json_schema_extra={"examples": ["550e8400-e29b-41d4-a716-446655440000"]},
    )
    device_ids: list[UUID] | None = Field(
        default=None,
        description="指定设备ID列表（可选）。若提供，将纳入这些设备的 IP 作为扫描目标",
        json_schema_extra={"examples": [["550e8400-e29b-41d4-a716-446655440000"]]},
    )
    ports: str | None = Field(
        default=None,
        description="可选：扫描端口（覆盖默认 SCAN_DEFAULT_PORTS），例如 22,80,443",
        json_schema_extra={"examples": ["22,80,443"]},
    )

    @field_validator("subnets")
    @classmethod
    def validate_subnets(cls, v: list[str] | None) -> list[str] | None:
        if not v:
            return v
        import ipaddress

        cleaned: list[str] = []
        for s in v:
            s2 = (s or "").strip()
            if not s2:
                continue
            try:
                ipaddress.ip_network(s2, strict=False)
            except ValueError as e:
                raise ValueError(f"无效的 CIDR: {s2}") from e
            cleaned.append(s2)
        return cleaned or None

    @model_validator(mode="after")
    def validate_scope(self) -> "InventoryAuditScope":
        if not self.subnets and not self.dept_id and not self.device_ids:
            raise ValueError("scope 至少需要提供 subnets / dept_id / device_ids 之一")
        return self


class InventoryAuditCreate(BaseModel):
    """创建盘点任务请求体。"""

    name: str = Field(..., min_length=1, max_length=200, description="盘点任务名称")
    scope: InventoryAuditScope = Field(
        ...,
        description="盘点范围",
        json_schema_extra={
            "examples": [
                {
                    "name": "盘点-园区A",
                    "scope": {"subnets": ["192.168.1.0/24"], "ports": "22,80,443"},
                },
                {
                    "name": "盘点-某部门",
                    "scope": {"dept_id": "550e8400-e29b-41d4-a716-446655440000"},
                },
                {
                    "name": "盘点-指定设备",
                    "scope": {"device_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
                },
            ]
        },
    )


class InventoryAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    scope: dict
    status: str
    result: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    operator_id: UUID | None = None
    celery_task_id: str | None = None
    created_at: datetime
    updated_at: datetime


class InventoryAuditListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: InventoryAuditStatus | None = None

