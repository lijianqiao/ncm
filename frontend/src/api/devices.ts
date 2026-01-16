/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: devices.ts
 * @DateTime: 2026-01-10
 * @Docs: 设备管理 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type {
  DeviceVendorType,
  DeviceStatusType,
  DeviceGroupType,
  AuthTypeType,
} from '@/types/enums'
import type { AxiosResponse } from 'axios'

// ==================== 类型重导出（兼容现有代码） ====================

export type DeviceVendor = DeviceVendorType
export type DeviceStatus = DeviceStatusType
export type DeviceGroup = DeviceGroupType
export type AuthType = AuthTypeType

// ==================== 接口定义 ====================

/** 部门简要信息 */
export interface DeptSimple {
  id: string
  name: string
  code: string
  parent_id: string | null
}

/** 设备响应接口 */
export interface Device {
  id: string
  name: string
  ip_address: string
  vendor: DeviceVendor | null
  model: string | null
  platform: string | null
  location: string | null
  description: string | null
  ssh_port: number
  auth_type: AuthType
  dept_id: string | null
  dept: DeptSimple | null
  device_group: DeviceGroup | null
  status: DeviceStatus
  serial_number: string | null
  os_version: string | null
  stock_in_at: string | null
  assigned_to: string | null
  retired_at: string | null
  last_backup_at: string | null
  last_online_at: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string | null
}

/** 创建设备参数 */
export interface DeviceCreate {
  name: string
  ip_address: string
  vendor?: DeviceVendor
  model?: string
  platform?: string
  location?: string
  description?: string
  ssh_port?: number
  auth_type?: AuthType
  dept_id?: string
  device_group?: DeviceGroup
  status?: DeviceStatus
  username?: string
  password?: string
  serial_number?: string
  os_version?: string
  stock_in_at?: string
  assigned_to?: string
}

/** 更新设备参数 */
export type DeviceUpdate = Partial<DeviceCreate> & {
  retired_at?: string
}

/** 设备查询参数 */
export interface DeviceSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  vendor?: DeviceVendor
  status?: DeviceStatus
  device_group?: DeviceGroup
  dept_id?: string
}

/** 批量创建结果 */
export interface DeviceBatchResult {
  success_count: number
  failed_count: number
  failed_items: Array<{ index: number; error: string }>
}

/** 设备状态流转请求 */
export interface DeviceStatusTransitionRequest {
  to_status: DeviceStatus
  reason?: string
}

/** 生命周期统计响应 */
export interface DeviceLifecycleStatsResponse {
  stock: number
  running: number
  maintenance: number
  retired: number
  total: number
}

export interface ImportErrorItem {
  row_number: number
  field: string | null
  message: string
}

export interface ImportValidateResponse {
  import_id: string
  checksum: string
  total_rows: number
  valid_rows: number
  error_rows: number
  errors: ImportErrorItem[]
}

export interface ImportPreviewRow {
  row_number: number
  data: Record<string, unknown>
}

export interface ImportPreviewResponse {
  import_id: string
  checksum: string
  page: number
  page_size: number
  total_rows: number
  rows: ImportPreviewRow[]
}

export interface ImportCommitRequest {
  import_id: string
  checksum: string
  allow_overwrite?: boolean
}

export interface ImportCommitResponse {
  import_id: string
  checksum: string
  status: string
  imported_rows: number
  created_at: string
}

// ==================== API 函数 ====================

/** 获取设备列表 */
export function getDevices(params?: DeviceSearchParams) {
  return request<ResponseBase<PaginatedResponse<Device>>>({
    url: '/devices/',
    method: 'get',
    params,
  })
}

/** 获取设备详情 */
export function getDevice(id: string) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}`,
    method: 'get',
  })
}

/** 创建设备 */
export function createDevice(data: DeviceCreate) {
  return request<ResponseBase<Device>>({
    url: '/devices/',
    method: 'post',
    data,
  })
}

/** 更新设备 */
export function updateDevice(id: string, data: DeviceUpdate) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}`,
    method: 'put',
    data,
  })
}

/** 删除设备 */
export function deleteDevice(id: string) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}`,
    method: 'delete',
  })
}

/** 批量创建设备 */
export function batchCreateDevices(devices: DeviceCreate[]) {
  return request<ResponseBase<DeviceBatchResult>>({
    url: '/devices/batch',
    method: 'post',
    data: { devices },
  })
}

/** 批量删除设备 */
export function batchDeleteDevices(ids: string[]) {
  return request<ResponseBase<DeviceBatchResult>>({
    url: '/devices/batch',
    method: 'delete',
    data: { ids },
  })
}

/** 获取回收站设备 */
export function getRecycleBinDevices(params?: DeviceSearchParams) {
  return request<ResponseBase<PaginatedResponse<Device>>>({
    url: '/devices/recycle-bin',
    method: 'get',
    params,
  })
}

/** 恢复设备 */
export function restoreDevice(id: string) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复设备 */
export function batchRestoreDevices(ids: string[]) {
  return request<ResponseBase<DeviceBatchResult>>({
    url: '/devices/batch/restore',
    method: 'post',
    data: { ids },
  })
}

/** 设备状态流转 */
export function transitionDeviceStatus(id: string, toStatus: DeviceStatus, reason?: string) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}/status/transition`,
    method: 'post',
    data: { to_status: toStatus, reason },
  })
}

export function exportDevices(fmt: 'csv' | 'xlsx' = 'csv') {
  return request<AxiosResponse<Blob>>({
    url: '/devices/export',
    method: 'get',
    params: { fmt },
    responseType: 'blob',
  })
}

export function downloadDeviceImportTemplate() {
  return request<AxiosResponse<Blob>>({
    url: '/devices/import/template',
    method: 'get',
    responseType: 'blob',
  })
}

export function uploadDeviceImportFile(file: File, allowOverwrite = false) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('allow_overwrite', allowOverwrite ? 'true' : 'false')
  return request<ResponseBase<ImportValidateResponse>>({
    url: '/devices/import/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function previewDeviceImport(params: {
  import_id: string
  checksum: string
  page?: number
  page_size?: number
  kind?: 'all' | 'valid'
}) {
  return request<ResponseBase<ImportPreviewResponse>>({
    url: '/devices/import/preview',
    method: 'get',
    params,
  })
}

export function commitDeviceImport(data: ImportCommitRequest) {
  return request<ResponseBase<ImportCommitResponse>>({
    url: '/devices/import/commit',
    method: 'post',
    data,
  })
}

/** 批量设备状态流转 */
export function batchTransitionDeviceStatus(
  ids: string[],
  toStatus: DeviceStatus,
  reason?: string,
) {
  return request<ResponseBase<DeviceBatchResult>>({
    url: '/devices/status/transition/batch',
    method: 'post',
    data: { ids, to_status: toStatus, reason },
  })
}

/** 获取设备生命周期统计 */
export function getDeviceLifecycleStats(params?: { dept_id?: string; vendor?: DeviceVendor }) {
  return request<ResponseBase<DeviceLifecycleStatsResponse>>({
    url: '/devices/lifecycle/stats',
    method: 'get',
    params,
  })
}

/** 获取设备选项列表（用于下拉选择，返回大页数据） */
export function getDeviceOptions(params?: { status?: DeviceStatus }) {
  return request<ResponseBase<PaginatedResponse<Device>>>({
    url: '/devices/',
    method: 'get',
    params: { page_size: 500, ...params },
  })
}

// ==================== 彻底删除 API ====================

/** 彻底删除设备 */
export function hardDeleteDevice(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/devices/${id}/hard`,
    method: 'delete',
  })
}

/** 批量彻底删除设备 */
export function batchHardDeleteDevices(ids: string[]) {
  return request<ResponseBase<DeviceBatchResult>>({
    url: '/devices/batch/hard',
    method: 'delete',
    data: { ids },
  })
}
