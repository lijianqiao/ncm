/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: enum-labels.ts
 * @DateTime: 2026-01-10
 * @Docs: 枚举标签与选项配置（用于 UI 展示）
 */

import {
  DeviceVendor,
  DeviceGroup,
  AuthType,
  DeviceStatus,
  DeviceType,
  BackupType,
  BackupStatus,
  TaskStatus,
  InventoryAuditStatus,
  TemplateType,
  TemplateStatus,
  DiscoveryStatus,
  AlertType,
  AlertSeverity,
  AlertStatus,
} from './enums'

// ===== 标签映射 =====

/** 设备厂商标签 */
export const DeviceVendorLabels: Record<DeviceVendor, string> = {
  [DeviceVendor.H3C]: 'H3C',
  [DeviceVendor.HUAWEI]: 'Huawei',
  [DeviceVendor.CISCO]: 'Cisco',
  [DeviceVendor.OTHER]: '其他',
}

/** 设备分组标签 */
export const DeviceGroupLabels: Record<DeviceGroup, string> = {
  [DeviceGroup.CORE]: '核心层',
  [DeviceGroup.DISTRIBUTION]: '汇聚层',
  [DeviceGroup.ACCESS]: '接入层',
}

/** 认证类型标签 */
export const AuthTypeLabels: Record<AuthType, string> = {
  [AuthType.STATIC]: '静态密码',
  [AuthType.OTP_SEED]: 'OTP种子',
  [AuthType.OTP_MANUAL]: 'OTP手动',
}

/** 设备状态标签 */
export const DeviceStatusLabels: Record<DeviceStatus, string> = {
  [DeviceStatus.IN_STOCK]: '在库',
  [DeviceStatus.IN_USE]: '在用',
  [DeviceStatus.ACTIVE]: '在线',
  [DeviceStatus.MAINTENANCE]: '维护中',
  [DeviceStatus.RETIRED]: '已报废',
}

/** 设备类型标签 */
export const DeviceTypeLabels: Record<DeviceType, string> = {
  [DeviceType.SWITCH]: '交换机',
  [DeviceType.ROUTER]: '路由器',
  [DeviceType.FIREWALL]: '防火墙',
  [DeviceType.ALL]: '全部',
}

/** 备份类型标签 */
export const BackupTypeLabels: Record<BackupType, string> = {
  [BackupType.SCHEDULED]: '定时备份',
  [BackupType.MANUAL]: '手动备份',
  [BackupType.PRE_CHANGE]: '变更前备份',
  [BackupType.POST_CHANGE]: '变更后备份',
  [BackupType.INCREMENTAL]: '增量备份',
}

/** 备份状态标签 */
export const BackupStatusLabels: Record<BackupStatus, string> = {
  [BackupStatus.SUCCESS]: '成功',
  [BackupStatus.FAILED]: '失败',
  [BackupStatus.PARTIAL]: '部分成功',
}

/** 任务状态标签 */
export const TaskStatusLabels: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '待审批',
  [TaskStatus.APPROVED]: '已审批',
  [TaskStatus.REJECTED]: '已拒绝',
  [TaskStatus.RUNNING]: '执行中',
  [TaskStatus.PAUSED]: '已暂停',
  [TaskStatus.SUCCESS]: '成功',
  [TaskStatus.FAILED]: '失败',
  [TaskStatus.PARTIAL]: '部分成功',
  [TaskStatus.CANCELLED]: '已取消',
  [TaskStatus.ROLLBACK]: '已回滚',
}

/** 盘点任务状态标签 */
export const InventoryAuditStatusLabels: Record<InventoryAuditStatus, string> = {
  [InventoryAuditStatus.PENDING]: '待执行',
  [InventoryAuditStatus.RUNNING]: '执行中',
  [InventoryAuditStatus.SUCCESS]: '成功',
  [InventoryAuditStatus.FAILED]: '失败',
}

/** 模板类型标签 */
export const TemplateTypeLabels: Record<TemplateType, string> = {
  [TemplateType.VLAN]: 'VLAN配置',
  [TemplateType.INTERFACE]: '接口配置',
  [TemplateType.ACL]: 'ACL策略',
  [TemplateType.ROUTE]: '路由配置',
  [TemplateType.QOS]: 'QoS策略',
  [TemplateType.CUSTOM]: '自定义',
}

/** 模板状态标签 */
export const TemplateStatusLabels: Record<TemplateStatus, string> = {
  [TemplateStatus.DRAFT]: '草稿',
  [TemplateStatus.PENDING]: '待审批',
  [TemplateStatus.APPROVED]: '已审批',
  [TemplateStatus.REJECTED]: '已拒绝',
  [TemplateStatus.DEPRECATED]: '已废弃',
}

/** 发现状态标签 */
export const DiscoveryStatusLabels: Record<DiscoveryStatus, string> = {
  [DiscoveryStatus.MATCHED]: '已匹配',
  [DiscoveryStatus.PENDING]: '待确认',
  [DiscoveryStatus.SHADOW]: '影子资产',
  [DiscoveryStatus.OFFLINE]: '离线',
}

/** 告警类型标签 */
export const AlertTypeLabels: Record<AlertType, string> = {
  [AlertType.CONFIG_CHANGE]: '配置变更',
  [AlertType.DEVICE_OFFLINE]: '设备离线',
  [AlertType.SHADOW_ASSET]: '影子资产',
}

/** 告警级别标签 */
export const AlertSeverityLabels: Record<AlertSeverity, string> = {
  [AlertSeverity.LOW]: '低',
  [AlertSeverity.MEDIUM]: '中',
  [AlertSeverity.HIGH]: '高',
}

/** 告警状态标签 */
export const AlertStatusLabels: Record<AlertStatus, string> = {
  [AlertStatus.OPEN]: '未处理',
  [AlertStatus.ACK]: '已确认',
  [AlertStatus.CLOSED]: '已关闭',
}

// ===== 选项生成工具 =====

type OptionItem = { label: string; value: string }

/** 从枚举和标签生成下拉选项 */
function enumToOptions<T extends string>(
  enumObj: Record<string, T>,
  labels: Record<T, string>,
): OptionItem[] {
  return Object.values(enumObj).map((value) => ({
    label: labels[value],
    value: value,
  }))
}

// ===== 预生成的选项（用于 NSelect 等组件） =====

export const DeviceVendorOptions = enumToOptions(DeviceVendor, DeviceVendorLabels)
export const DeviceGroupOptions = enumToOptions(DeviceGroup, DeviceGroupLabels)
export const AuthTypeOptions = enumToOptions(AuthType, AuthTypeLabels)
export const DeviceStatusOptions = enumToOptions(DeviceStatus, DeviceStatusLabels)
export const DeviceTypeOptions = enumToOptions(DeviceType, DeviceTypeLabels)
export const BackupTypeOptions = enumToOptions(BackupType, BackupTypeLabels)
export const BackupStatusOptions = enumToOptions(BackupStatus, BackupStatusLabels)
export const TaskStatusOptions = enumToOptions(TaskStatus, TaskStatusLabels)
export const InventoryAuditStatusOptions = enumToOptions(InventoryAuditStatus, InventoryAuditStatusLabels)
export const TemplateTypeOptions = enumToOptions(TemplateType, TemplateTypeLabels)
export const TemplateStatusOptions = enumToOptions(TemplateStatus, TemplateStatusLabels)
export const DiscoveryStatusOptions = enumToOptions(DiscoveryStatus, DiscoveryStatusLabels)
export const AlertTypeOptions = enumToOptions(AlertType, AlertTypeLabels)
export const AlertSeverityOptions = enumToOptions(AlertSeverity, AlertSeverityLabels)
export const AlertStatusOptions = enumToOptions(AlertStatus, AlertStatusLabels)

// ===== 颜色映射（用于 NTag 等组件） =====

export type TagType = 'default' | 'info' | 'success' | 'warning' | 'error'

/** 设备状态颜色 */
export const DeviceStatusColors: Record<DeviceStatus, TagType> = {
  [DeviceStatus.IN_STOCK]: 'default',
  [DeviceStatus.IN_USE]: 'info',
  [DeviceStatus.ACTIVE]: 'success',
  [DeviceStatus.MAINTENANCE]: 'warning',
  [DeviceStatus.RETIRED]: 'error',
}

/** 备份状态颜色 */
export const BackupStatusColors: Record<BackupStatus, TagType> = {
  [BackupStatus.SUCCESS]: 'success',
  [BackupStatus.FAILED]: 'error',
  [BackupStatus.PARTIAL]: 'warning',
}

/** 任务状态颜色 */
export const TaskStatusColors: Record<TaskStatus, TagType> = {
  [TaskStatus.PENDING]: 'default',
  [TaskStatus.APPROVED]: 'info',
  [TaskStatus.REJECTED]: 'error',
  [TaskStatus.RUNNING]: 'warning',
  [TaskStatus.PAUSED]: 'warning',
  [TaskStatus.SUCCESS]: 'success',
  [TaskStatus.FAILED]: 'error',
  [TaskStatus.PARTIAL]: 'warning',
  [TaskStatus.CANCELLED]: 'default',
  [TaskStatus.ROLLBACK]: 'warning',
}

/** 盘点状态颜色 */
export const InventoryAuditStatusColors: Record<InventoryAuditStatus, TagType> = {
  [InventoryAuditStatus.PENDING]: 'default',
  [InventoryAuditStatus.RUNNING]: 'info',
  [InventoryAuditStatus.SUCCESS]: 'success',
  [InventoryAuditStatus.FAILED]: 'error',
}

/** 模板状态颜色 */
export const TemplateStatusColors: Record<TemplateStatus, TagType> = {
  [TemplateStatus.DRAFT]: 'default',
  [TemplateStatus.PENDING]: 'info',
  [TemplateStatus.APPROVED]: 'success',
  [TemplateStatus.REJECTED]: 'error',
  [TemplateStatus.DEPRECATED]: 'warning',
}

/** 发现状态颜色 */
export const DiscoveryStatusColors: Record<DiscoveryStatus, TagType> = {
  [DiscoveryStatus.MATCHED]: 'success',
  [DiscoveryStatus.PENDING]: 'info',
  [DiscoveryStatus.SHADOW]: 'warning',
  [DiscoveryStatus.OFFLINE]: 'error',
}

/** 告警级别颜色 */
export const AlertSeverityColors: Record<AlertSeverity, TagType> = {
  [AlertSeverity.LOW]: 'info',
  [AlertSeverity.MEDIUM]: 'warning',
  [AlertSeverity.HIGH]: 'error',
}

/** 告警状态颜色 */
export const AlertStatusColors: Record<AlertStatus, TagType> = {
  [AlertStatus.OPEN]: 'error',
  [AlertStatus.ACK]: 'warning',
  [AlertStatus.CLOSED]: 'success',
}
