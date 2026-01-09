from app.core.enums import (
    ApprovalStatus,
    AuthType,
    BackupStatus,
    BackupType,
    DeviceGroup,
    DeviceStatus,
    DeviceType,
    DeviceVendor,
    DiscoveryStatus,
    TaskStatus,
    TaskType,
    TemplateStatus,
    TemplateType,
)

from .alert import Alert
from .backup import Backup
from .base import AuditableModel, Base
from .credential import DeviceGroupCredential
from .dept import Department
from .device import Device
from .discovery import Discovery
from .inventory_audit import InventoryAudit
from .log import LoginLog, OperationLog
from .rbac import Menu, Role, RoleMenu, UserRole
from .task import Task
from .task_approval import TaskApprovalStep
from .template import Template
from .topology import TopologyLink
from .user import User

__all__ = [
    # 基础模型
    "Base",
    "AuditableModel",
    # 用户与权限
    "User",
    "Role",
    "Menu",
    "UserRole",
    "RoleMenu",
    "Department",
    # 日志
    "LoginLog",
    "OperationLog",
    # 网络设备管理 (NCM)
    "Device",
    "DeviceVendor",
    "DeviceGroup",
    "AuthType",
    "DeviceStatus",
    # 凭据管理
    "DeviceGroupCredential",
    # 配置备份
    "Backup",
    "BackupType",
    "BackupStatus",
    # 任务管理
    "Task",
    "TaskType",
    "TaskStatus",
    "ApprovalStatus",
    "TaskApprovalStep",
    # 配置模板
    "Template",
    "TemplateType",
    "TemplateStatus",
    "DeviceType",
    # 设备发现
    "Discovery",
    "DiscoveryStatus",
    # 资产盘点
    "InventoryAudit",
    # 告警
    "Alert",
    # 网络拓扑
    "TopologyLink",
]
