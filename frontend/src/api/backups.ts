/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: backups.ts
 * @DateTime: 2026-01-10
 * @Docs: 配置备份 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type { BackupTypeType } from '@/types/enums'
import type { AxiosResponse } from 'axios'

// 重新导出枚举类型供外部使用
export type { BackupTypeType as BackupType }

// ==================== 接口定义 ====================

/** 备份响应接口 */
export interface Backup {
  id: string
  device_id: string
  backup_type: BackupTypeType
  status: string
  content_size: number
  md5_hash: string | null
  error_message: string | null
  operator_id?: string | null
  created_at: string
  updated_at: string
  has_content?: boolean
  device?: {
    id: string
    name: string
    ip_address: string
    vendor?: string | null
    model?: string | null
    device_group?: string | null
    auth_type?: string | null
    location?: string | null
    dept?: { id: string; name: string; code?: string | null; parent_id?: string | null } | null
  } | null

  // 兼容旧字段（避免历史代码/缓存数据导致运行时异常）
  device_name?: string | null
  config_hash?: string
  file_size?: number
}

/** 备份内容响应 */
export interface BackupContentResponse {
  id: string
  device_id: string
  content: string
  content_size: number
  md5_hash: string | null
}

/** 备份查询参数 */
export interface BackupSearchParams {
  page?: number
  page_size?: number
  device_id?: string
  backup_type?: BackupTypeType
  keyword?: string // 搜索设备名称、IP
  device_group?: string
  auth_type?: string
  device_status?: string
  vendor?: string
}

/** 批量备份请求 */
export interface BatchBackupRequest {
  device_ids: string[]
  backup_type?: BackupTypeType
  resume_task_id?: string
  skip_device_ids?: string[]
}

/** OTP 通知结构 */
export interface OTPNotice {
  type?: string
  message?: string
  dept_id: string
  device_group: string
  failed_devices?: Array<{ name: string; error: string }>
  pending_device_ids?: string[]
}

/** 批量备份结果 */
export interface BackupBatchResult {
  task_id: string
  total: number
  /** 同步接口返回 */
  success_count?: number
  failed_count?: number
  failed_devices?: Array<{ device_id: string; error: string }>
  /** 异步任务返回 */
  success?: number
  failed?: number
  /** 设备级别的详细结果（异步任务返回） */
  results?: Record<string, { status: string; error?: string; result?: unknown }>
}

/** 备份任务状态 */
export interface BackupTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failed'

  // 进度信息
  progress?:
  | number
  | {
    stage: string
    message: string
  }

  // 进度数值（用于进度条）
  completed?: number // 已完成设备数
  total?: number // 总设备数
  percent?: number // 百分比 0-100

  // 完成后的统计
  total_devices?: number
  success_count?: number
  failed_count?: number
  failed_devices?: Array<{ name: string; error: string }>

  // OTP 相关
  otp_notice?: OTPNotice

  // 兼容旧字段
  result?: BackupBatchResult | null
  error?: string | null
}

export interface BackupBatchDeleteRequest {
  backup_ids: string[]
}

export interface BackupBatchDeleteResult {
  success_count: number
  failed_ids: string[]
}

export interface BackupBatchRestoreRequest {
  backup_ids: string[]
}

export interface BackupBatchRestoreResult {
  success_count: number
  failed_ids: string[]
}

export interface BackupBatchHardDeleteRequest {
  backup_ids: string[]
}

export interface BackupBatchHardDeleteResult {
  success_count: number
  failed_ids: string[]
}

// ==================== API 函数 ====================

/** 获取备份列表 */
export function getBackups(params?: BackupSearchParams) {
  return request<ResponseBase<PaginatedResponse<Backup>>>({
    url: '/backups/',
    method: 'get',
    params,
  })
}

/** 获取备份详情 */
export function getBackup(id: string) {
  return request<ResponseBase<Backup>>({
    url: `/backups/${id}`,
    method: 'get',
  })
}

/** 获取备份配置内容 */
export function getBackupContent(id: string) {
  return request<ResponseBase<BackupContentResponse>>({
    url: `/backups/${id}/content`,
    method: 'get',
  })
}

/** 删除备份 */
export function deleteBackup(id: string) {
  return request<ResponseBase<unknown>>({
    url: `/backups/${id}`,
    method: 'delete',
  })
}

/** 批量删除备份（软删除） */
export function batchDeleteBackups(data: BackupBatchDeleteRequest) {
  return request<ResponseBase<BackupBatchDeleteResult>>({
    url: '/backups/batch',
    method: 'delete',
    data,
  })
}

/** 获取回收站备份列表 */
export function getRecycleBackups(params?: BackupSearchParams) {
  return request<ResponseBase<PaginatedResponse<Backup>>>({
    url: '/backups/recycle-bin',
    method: 'get',
    params,
  })
}

/** 恢复备份 */
export function restoreBackup(id: string) {
  return request<ResponseBase<{ id: string; restored: boolean }>>({
    url: `/backups/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复备份 */
export function batchRestoreBackups(data: BackupBatchRestoreRequest) {
  return request<ResponseBase<BackupBatchRestoreResult>>({
    url: '/backups/batch/restore',
    method: 'post',
    data,
  })
}

/** 硬删除备份 */
export function hardDeleteBackup(id: string) {
  return request<ResponseBase<{ id: string; hard_deleted: boolean }>>({
    url: `/backups/${id}/hard`,
    method: 'delete',
  })
}

/** 批量硬删除备份 */
export function batchHardDeleteBackups(data: BackupBatchHardDeleteRequest) {
  return request<ResponseBase<BackupBatchHardDeleteResult>>({
    url: '/backups/batch/hard',
    method: 'delete',
    data,
  })
}

/** 手动备份单设备 */
export function backupDevice(
  deviceId: string,
  data?: { backup_type?: BackupTypeType; otp_code?: string },
) {
  return request<ResponseBase<Backup>>({
    url: `/backups/device/${deviceId}`,
    method: 'post',
    data: data ?? {},
    // 手动备份属于长耗时操作（设备侧执行 show current-config 可能 10s+）
    timeout: 60_000,
  })
}

/** 批量备份设备 */
export function batchBackup(data: BatchBackupRequest) {
  return request<ResponseBase<BackupBatchResult>>({
    url: '/backups/batch',
    method: 'post',
    data,
  })
}

/** 查询备份任务状态 */
export function getBackupTaskStatus(taskId: string) {
  return request<ResponseBase<BackupTaskStatus>>({
    url: `/backups/task/${taskId}`,
    method: 'get',
  })
}

/** 获取设备最新备份 */
export function getDeviceLatestBackup(deviceId: string) {
  return request<ResponseBase<Backup>>({
    url: `/backups/device/${deviceId}/latest`,
    method: 'get',
  })
}

/** 获取设备备份历史 */
export function getDeviceBackupHistory(
  deviceId: string,
  params?: { page?: number; page_size?: number },
) {
  return request<ResponseBase<PaginatedResponse<Backup>>>({
    url: `/backups/device/${deviceId}/history`,
    method: 'get',
    params,
  })
}

/** 下载备份配置文件 */
export function downloadBackup(id: string) {
  // 返回下载 URL，由前端处理下载
  return `/backups/${id}/download`
}

export function exportBackups(fmt: 'csv' | 'xlsx' = 'csv') {
  return request<AxiosResponse<Blob>>({
    url: '/backups/export',
    method: 'get',
    params: { fmt },
    responseType: 'blob',
  })
}
