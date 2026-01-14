/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: discovery.ts
 * @DateTime: 2026-01-10
 * @Docs: 资产发现 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type { DiscoveryStatusType } from '@/types/enums'

// 重新导出枚举类型供外部使用
export type { DiscoveryStatusType as DiscoveryStatus }

// ==================== 接口定义 ====================

/** 发现记录响应接口 */
export interface DiscoveryRecord {
  id: string
  ip_address: string
  mac_address: string | null
  vendor: string | null
  device_type: string | null
  hostname: string | null
  os_info: string | null
  open_ports: Record<string, string> | null
  ssh_banner: string | null
  first_seen_at: string
  last_seen_at: string
  offline_days: number
  status: DiscoveryStatusType
  matched_device_id: string | null
  matched_device_name: string | null
  matched_device_ip: string | null
  scan_source: string | null
  created_at: string
  updated_at: string
}

/** 发现记录查询参数 */
export interface DiscoverySearchParams {
  page?: number
  page_size?: number
  status?: DiscoveryStatusType
  keyword?: string
  scan_source?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

/** 扫描请求 */
export interface ScanRequest {
  subnets: string[]
  scan_type?: 'auto' | 'nmap' | 'masscan'
  ports?: string
  async_mode?: boolean
}

/** 扫描结果 */
export interface ScanResult {
  task_id?: string | null
  subnet: string
  scan_type: string
  hosts_found: number
  hosts: unknown[]
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  error: string | null
}

export interface ScanSubnetSummary {
  subnet: string
  hosts_found: number
  error: string | null
}

export interface ScanBatchResult {
  task_id: string
  total_subnets: number
  total_hosts: number
  results: ScanSubnetSummary[]
}

/** 扫描任务响应 */
export interface ScanTaskResponse {
  task_id: string
  status: string
  message: string
}

/** 扫描任务状态 */
export interface ScanTaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED'
  progress: number
  result: ScanResult | ScanBatchResult | null
  error: string | null
}

/** 纳管设备请求 */
export interface AdoptDeviceRequest {
  name: string
  vendor?: string
  device_group?: string
  dept_id?: string
  username?: string
  password?: string
}

/** 离线设备 */
export interface OfflineDevice {
  device_id: string
  device_name: string
  ip_address: string
  last_seen_at: string
  offline_days: number
}

// ==================== API 函数 ====================

/** 触发网络扫描 */
export function triggerScan(data: ScanRequest) {
  return request<ResponseBase<ScanTaskResponse>>({
    url: '/discovery/scan',
    method: 'post',
    data,
  })
}

/** 查询扫描任务状态 */
export function getScanTaskStatus(taskId: string) {
  return request<ResponseBase<ScanTaskStatus>>({
    url: `/discovery/scan/task/${taskId}`,
    method: 'get',
  })
}

/** 获取发现记录列表 */
export function getDiscoveryRecords(params?: DiscoverySearchParams) {
  return request<ResponseBase<PaginatedResponse<DiscoveryRecord>>>({
    url: '/discovery/',
    method: 'get',
    params,
  })
}

/** 获取发现记录详情 */
export function getDiscoveryRecord(id: string) {
  return request<ResponseBase<DiscoveryRecord>>({
    url: `/discovery/${id}`,
    method: 'get',
  })
}

/** 删除发现记录 */
export function deleteDiscoveryRecord(id: string) {
  return request<ResponseBase<{ message: string }>>({
    url: `/discovery/${id}`,
    method: 'delete',
  })
}

/** 纳管设备 */
export function adoptDevice(discoveryId: string, data: AdoptDeviceRequest) {
  return request<ResponseBase<{ message: string; device_id: string; device_name: string }>>({
    url: `/discovery/${discoveryId}/adopt`,
    method: 'post',
    data,
  })
}

/** 获取影子资产列表 */
export function getShadowAssets(params?: { page?: number; page_size?: number }) {
  return request<ResponseBase<PaginatedResponse<DiscoveryRecord>>>({
    url: '/discovery/shadow',
    method: 'get',
    params,
  })
}

/** 获取离线设备列表 */
export function getOfflineDevices(daysThreshold?: number) {
  return request<ResponseBase<OfflineDevice[]>>({
    url: '/discovery/offline',
    method: 'get',
    params: daysThreshold ? { days_threshold: daysThreshold } : undefined,
  })
}

/** 执行 CMDB 比对 */
export function compareCMDB(asyncMode: boolean = true) {
  return request<ResponseBase<ScanTaskResponse>>({
    url: '/discovery/compare',
    method: 'post',
    params: { async_mode: asyncMode },
  })
}
