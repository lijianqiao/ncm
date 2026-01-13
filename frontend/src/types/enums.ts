/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: enums.ts
 * @DateTime: 2026-01-10
 * @Docs: 前端枚举常量定义（与后端 app/core/enums.py 保持一致）
 */

// ===== 系统管理相关枚举 =====

/** 菜单节点类型 */
export enum MenuType {
  CATALOG = 'CATALOG',
  MENU = 'MENU',
  PERMISSION = 'PERMISSION',
}

/** 数据权限范围 */
export enum DataScope {
  ALL = 'ALL',
  CUSTOM = 'CUSTOM',
  DEPT = 'DEPT',
  DEPT_AND_CHILDREN = 'DEPT_AND_CHILDREN',
  SELF = 'SELF',
}

// ===== NCM 网络设备管理相关枚举 =====

/** 设备厂商 */
export enum DeviceVendor {
  H3C = 'h3c',
  HUAWEI = 'huawei',
  CISCO = 'cisco',
  OTHER = 'other',
}

/** 设备分组（核心/汇聚/接入） */
export enum DeviceGroup {
  CORE = 'core',
  DISTRIBUTION = 'distribution',
  ACCESS = 'access',
}

/** 认证类型 */
export enum AuthType {
  STATIC = 'static',
  OTP_SEED = 'otp_seed',
  OTP_MANUAL = 'otp_manual',
}

/** 设备生命周期状态 */
export enum DeviceStatus {
  IN_STOCK = 'in_stock',
  IN_USE = 'in_use',
  ACTIVE = 'active',
  MAINTENANCE = 'maintenance',
  RETIRED = 'retired',
}

/** 设备类型 */
export enum DeviceType {
  SWITCH = 'switch',
  ROUTER = 'router',
  FIREWALL = 'firewall',
  ALL = 'all',
}

// ===== NCM 备份相关枚举 =====

/** 备份类型 */
export enum BackupType {
  SCHEDULED = 'scheduled',
  MANUAL = 'manual',
  PRE_CHANGE = 'pre_change',
  POST_CHANGE = 'post_change',
  INCREMENTAL = 'incremental',
}

/** 备份状态 */
export enum BackupStatus {
  SUCCESS = 'success',
  FAILED = 'failed',
  PARTIAL = 'partial',
}

// ===== NCM 任务相关枚举 =====

/** 任务类型 */
export enum TaskType {
  BACKUP = 'backup',
  DEPLOY = 'deploy',
  DISCOVERY = 'discovery',
  TOPOLOGY = 'topology',
}

/** 任务状态 */
export enum TaskStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  RUNNING = 'running',
  PAUSED = 'paused',
  SUCCESS = 'success',
  FAILED = 'failed',
  PARTIAL = 'partial',
  CANCELLED = 'cancelled',
  ROLLBACK = 'rollback',
}

// ===== 盘点相关枚举 =====

/** 盘点任务状态 */
export enum InventoryAuditStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILED = 'failed',
}

/** 审批状态 */
export enum ApprovalStatus {
  NONE = 'none',
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
}

// ===== NCM 模板相关枚举 =====

/** 模板类型 */
export enum TemplateType {
  VLAN = 'vlan',
  INTERFACE = 'interface',
  ACL = 'acl',
  ROUTE = 'route',
  QOS = 'qos',
  CUSTOM = 'custom',
}

/** 模板状态 */
export enum TemplateStatus {
  DRAFT = 'draft',
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  DEPRECATED = 'deprecated',
}

// ===== NCM 设备发现相关枚举 =====

/** 发现状态 */
export enum DiscoveryStatus {
  MATCHED = 'matched',
  PENDING = 'pending',
  SHADOW = 'shadow',
  OFFLINE = 'offline',
}

// ===== NCM 告警相关枚举 =====

/** 告警类型 */
export enum AlertType {
  CONFIG_CHANGE = 'config_change',
  DEVICE_OFFLINE = 'device_offline',
  SHADOW_ASSET = 'shadow_asset',
}

/** 告警级别 */
export enum AlertSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
}

/** 告警状态 */
export enum AlertStatus {
  OPEN = 'open',
  ACK = 'ack',
  CLOSED = 'closed',
}

// ===== 类型别名（用于 API 参数类型） =====

export type DeviceVendorType = `${DeviceVendor}`
export type DeviceGroupType = `${DeviceGroup}`
export type AuthTypeType = `${AuthType}`
export type DeviceStatusType = `${DeviceStatus}`
export type DeviceTypeType = `${DeviceType}`
export type BackupTypeType = `${BackupType}`
export type BackupStatusType = `${BackupStatus}`
export type TaskStatusType = `${TaskStatus}`
export type InventoryAuditStatusType = `${InventoryAuditStatus}`
export type TemplateTypeType = `${TemplateType}`
export type TemplateStatusType = `${TemplateStatus}`
export type DiscoveryStatusType = `${DiscoveryStatus}`
export type AlertTypeType = `${AlertType}`
export type AlertSeverityType = `${AlertSeverity}`
export type AlertStatusType = `${AlertStatus}`
