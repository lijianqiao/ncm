"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: enums.py
@DateTime: 2026-01-06 00:00:00
@Docs: 枚举常量定义（用于替代魔法字符串）。
"""

from enum import Enum


class MenuType(str, Enum):
    """菜单节点类型。"""

    CATALOG = "CATALOG"
    MENU = "MENU"
    PERMISSION = "PERMISSION"


class DataScope(str, Enum):
    """数据权限范围。"""

    ALL = "ALL"  # 全部数据
    CUSTOM = "CUSTOM"  # 自定义（基于角色分配）
    DEPT = "DEPT"  # 本部门
    DEPT_AND_CHILDREN = "DEPT_AND_CHILDREN"  # 本部门及下级
    SELF = "SELF"  # 仅本人


# ===== NCM 网络设备管理相关枚举 =====


class DeviceVendor(str, Enum):
    """设备厂商枚举。"""

    H3C = "h3c"
    HUAWEI = "huawei"
    CISCO = "cisco"
    OTHER = "other"


class DeviceGroup(str, Enum):
    """设备分组枚举（核心/汇聚/接入）。"""

    CORE = "core"
    DISTRIBUTION = "distribution"
    ACCESS = "access"


class AuthType(str, Enum):
    """认证类型枚举。"""

    STATIC = "static"  # 静态密码
    OTP_SEED = "otp_seed"  # OTP 种子存储（自动生成验证码）
    OTP_MANUAL = "otp_manual"  # OTP 手动输入（需要用户输入）


class DeviceStatus(str, Enum):
    """设备生命周期状态。"""

    IN_STOCK = "in_stock"  # 在库
    IN_USE = "in_use"  # 在用
    ACTIVE = "active"  # 活跃（可自动备份）
    MAINTENANCE = "maintenance"  # 维修中
    RETIRED = "retired"  # 报废


class DeviceType(str, Enum):
    """设备类型。"""

    SWITCH = "switch"  # 交换机
    ROUTER = "router"  # 路由器
    FIREWALL = "firewall"  # 防火墙
    ALL = "all"  # 所有类型


# ===== NCM 备份相关枚举 =====


class BackupType(str, Enum):
    """备份类型。"""

    SCHEDULED = "scheduled"  # 定时备份
    MANUAL = "manual"  # 手动备份
    PRE_CHANGE = "pre_change"  # 变更前备份
    INCREMENTAL = "incremental"  # 增量备份（配置变更检测触发）


class BackupStatus(str, Enum):
    """备份状态。"""

    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    PARTIAL = "partial"  # 部分成功


# ===== NCM 任务相关枚举 =====


class TaskType(str, Enum):
    """任务类型。"""

    BACKUP = "backup"  # 配置备份
    DEPLOY = "deploy"  # 配置下发
    DISCOVERY = "discovery"  # 设备发现
    TOPOLOGY = "topology"  # 拓扑采集


class TaskStatus(str, Enum):
    """任务状态。"""

    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已审批
    REJECTED = "rejected"  # 已拒绝
    RUNNING = "running"  # 执行中
    PAUSED = "paused"  # 已暂停（等待 OTP 输入等）
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    PARTIAL = "partial"  # 部分成功
    CANCELLED = "cancelled"  # 已取消
    ROLLBACK = "rollback"  # 已回滚


class ApprovalStatus(str, Enum):
    """审批状态。"""

    NONE = "none"  # 无需审批
    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝


# ===== NCM 模板相关枚举 =====


class TemplateType(str, Enum):
    """模板类型。"""

    VLAN = "vlan"  # VLAN 配置
    INTERFACE = "interface"  # 接口配置
    ACL = "acl"  # ACL 策略
    ROUTE = "route"  # 路由配置
    QOS = "qos"  # QoS 策略
    CUSTOM = "custom"  # 自定义


class TemplateStatus(str, Enum):
    """模板状态。"""

    DRAFT = "draft"  # 草稿
    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已审批
    REJECTED = "rejected"  # 已拒绝
    DEPRECATED = "deprecated"  # 已废弃


# ===== NCM 设备发现相关枚举 =====


class DiscoveryStatus(str, Enum):
    """发现状态。"""

    MATCHED = "matched"  # 已匹配（在 CMDB 中）
    PENDING = "pending"  # 待确认
    SHADOW = "shadow"  # 影子资产（未在 CMDB 中）
    OFFLINE = "offline"  # CMDB 中存在但扫描未发现


# ===== NCM 告警相关枚举 =====


class AlertType(str, Enum):
    """告警类型。"""

    CONFIG_CHANGE = "config_change"  # 配置变更
    DEVICE_OFFLINE = "device_offline"  # 设备离线
    SHADOW_ASSET = "shadow_asset"  # 影子资产


class AlertSeverity(str, Enum):
    """告警级别。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(str, Enum):
    """告警状态。"""

    OPEN = "open"
    ACK = "ack"
    CLOSED = "closed"