from .backup import Backup, BackupStatus, BackupType
from .base import AuditableModel, Base
from .credential import DeviceGroupCredential
from .dept import Department
from .device import AuthType, Device, DeviceGroup, DeviceStatus, DeviceVendor
from .discovery import Discovery, DiscoveryStatus
from .log import LoginLog, OperationLog
from .rbac import Menu, Role, RoleMenu, UserRole
from .task import ApprovalStatus, Task, TaskStatus, TaskType
from .template import DeviceType, Template, TemplateStatus, TemplateType
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
    # 配置模板
    "Template",
    "TemplateType",
    "TemplateStatus",
    "DeviceType",
    # 设备发现
    "Discovery",
    "DiscoveryStatus",
    # 网络拓扑
    "TopologyLink",
]
