/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: devices.ts
 * @DateTime: 2026-01-10
 * @Docs: 设备管理 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

// ==================== 枚举类型 ====================

/** 设备厂商 */
export type DeviceVendor = 'cisco' | 'huawei' | 'h3c' | 'ruijie' | 'other'

/** 设备状态 */
export type DeviceStatus = 'stock' | 'running' | 'maintenance' | 'retired'

/** 设备分组 */
export type DeviceGroup = 'core' | 'distribution' | 'access' | 'firewall' | 'wireless' | 'other'

/** 认证类型 */
export type AuthType = 'static' | 'dynamic'

// ==================== 接口定义 ====================

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
  dept_name: string | null
  device_group: DeviceGroup | null
  status: DeviceStatus
  serial_number: string | null
  os_version: string | null
  stock_in_at: string | null
  assigned_to: string | null
  retired_at: string | null
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

/** 设备状态流转 */
export function transitionDeviceStatus(id: string, toStatus: DeviceStatus, reason?: string) {
  return request<ResponseBase<Device>>({
    url: `/devices/${id}/status/transition`,
    method: 'post',
    data: { to_status: toStatus, reason },
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
