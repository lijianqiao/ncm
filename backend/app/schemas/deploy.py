"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deploy.py
@DateTime: 2026-01-09 23:30:00
@Docs: 配置下发相关 Schema。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TaskStatus


class DeployPlan(BaseModel):
    """下发计划参数（灰度/并发/安全开关）。"""

    batch_size: int = Field(default=20, ge=1, le=500, description="灰度批次大小")
    concurrency: int = Field(default=50, ge=1, le=500, description="并发数（Nornir num_workers）")
    strict_allowlist: bool = Field(default=False, description="是否开启严格白名单校验（更安全但更易误杀）")
    dry_run: bool = Field(default=False, description="仅渲染/校验，不实际下发")


class DeployCreateRequest(BaseModel):
    """创建下发任务请求。"""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    template_id: UUID = Field(..., description="模板ID")
    template_params: dict[str, Any] = Field(default_factory=dict, description="模板参数")
    device_ids: list[UUID] = Field(..., min_length=1, description="目标设备ID列表")

    change_description: str | None = Field(default=None, description="变更说明")
    impact_scope: str | None = Field(default=None, description="影响范围")
    rollback_plan: str | None = Field(default=None, description="回退方案")

    approver_ids: list[UUID] | None = Field(default=None, description="三级审批人ID列表（长度=3，可选）")
    deploy_plan: DeployPlan = Field(default_factory=DeployPlan)


class DeployApproveRequest(BaseModel):
    """审批某一级。"""

    level: int = Field(..., ge=1, le=3)
    approve: bool = Field(..., description="true=通过 false=拒绝")
    comment: str | None = None


class DeployExecuteResponse(BaseModel):
    task_id: UUID
    celery_task_id: str
    status: TaskStatus


class DeployApprovalRecord(BaseModel):
    """下发任务审批记录（单级）。"""

    model_config = ConfigDict(from_attributes=True)

    level: int
    approver_id: UUID | None = None
    approver_name: str | None = None
    status: str
    comment: str | None = None
    approved_at: datetime | None = None


class DeployTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    task_type: str
    status: str
    approval_status: str
    current_approval_level: int
    celery_task_id: str | None = None
    template_id: UUID | None = None
    template_name: str | None = None
    template_params: dict | None = None
    deploy_plan: dict | None = None
    target_devices: dict | None = None
    total_devices: int
    success_count: int
    failed_count: int
    result: dict | None = None
    error_message: str | None = None
    created_by: UUID | None = None
    created_by_name: str | None = None
    approvals: list[DeployApprovalRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DeployRollbackResponse(BaseModel):
    task_id: UUID
    celery_task_id: str
    status: TaskStatus
