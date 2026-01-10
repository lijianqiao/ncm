/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: backups.ts
 * @DateTime: 2026-01-10
 * @Docs: 配置备份 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

// ==================== 枚举类型 ====================

/** 备份类型 */
export type BackupType = 'running' | 'startup' | 'full'

// ==================== 接口定义 ====================

/** 备份响应接口 */
export interface Backup {
  id: string
  device_id: string
  device_name: string | null
  backup_type: BackupType
  config_hash: string
  file_size: number
  created_at: string
}

/** 备份内容响应 */
export interface BackupContentResponse {
  id: string
  device_name: string | null
  backup_type: BackupType
  content: string
  config_hash: string
  created_at: string
}

/** 备份查询参数 */
export interface BackupSearchParams {
  page?: number
  page_size?: number
  device_id?: string
  backup_type?: BackupType
}

/** 批量备份请求 */
export interface BatchBackupRequest {
  device_ids: string[]
  backup_type?: BackupType
  resume_task_id?: string
  skip_device_ids?: string[]
}

/** 批量备份结果 */
export interface BackupBatchResult {
  task_id: string
  total: number
  success_count: number
  failed_count: number
  failed_devices: Array<{ device_id: string; error: string }>
}

/** 备份任务状态 */
export interface BackupTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failed'
  progress: number
  result: BackupBatchResult | null
  error: string | null
}

// ==================== API 函数 ====================

/** 获取备份列表 */
export function getBackups(params?: BackupSearchParams) {
  return request<ResponseBase<PaginatedResponse<Backup>>>({
    url: '/backups/backups/',
    method: 'get',
    params,
  })
}

/** 获取备份详情 */
export function getBackup(id: string) {
  return request<ResponseBase<Backup>>({
    url: `/backups/backups/${id}`,
    method: 'get',
  })
}

/** 获取备份配置内容 */
export function getBackupContent(id: string) {
  return request<ResponseBase<BackupContentResponse>>({
    url: `/backups/backups/${id}/content`,
    method: 'get',
  })
}

/** 删除备份 */
export function deleteBackup(id: string) {
  return request<ResponseBase<unknown>>({
    url: `/backups/backups/${id}`,
    method: 'delete',
  })
}

/** 手动备份单设备 */
export function backupDevice(deviceId: string) {
  return request<ResponseBase<Backup>>({
    url: `/backups/backups/device/${deviceId}`,
    method: 'post',
    data: {},
  })
}

/** 批量备份设备 */
export function batchBackup(data: BatchBackupRequest) {
  return request<ResponseBase<BackupBatchResult>>({
    url: '/backups/backups/batch',
    method: 'post',
    data,
  })
}

/** 查询备份任务状态 */
export function getBackupTaskStatus(taskId: string) {
  return request<ResponseBase<BackupTaskStatus>>({
    url: `/backups/backups/task/${taskId}`,
    method: 'get',
  })
}

/** 获取设备最新备份 */
export function getDeviceLatestBackup(deviceId: string) {
  return request<ResponseBase<Backup>>({
    url: `/backups/backups/device/${deviceId}/latest`,
    method: 'get',
  })
}

/** 获取设备备份历史 */
export function getDeviceBackupHistory(
  deviceId: string,
  params?: { page?: number; page_size?: number },
) {
  return request<ResponseBase<PaginatedResponse<Backup>>>({
    url: `/backups/backups/device/${deviceId}/history`,
    method: 'get',
    params,
  })
}

/** 下载备份配置文件 */
export function downloadBackup(id: string) {
  // 返回下载 URL，由前端处理下载
  return `/backups/backups/${id}/download`
}
