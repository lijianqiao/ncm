/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: collect.ts
 * @DateTime: 2026-01-10
 * @Docs: ARP/MAC 采集 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

// ==================== 接口定义 ====================

/** ARP 表条目 */
export interface ARPEntry {
  ip_address: string
  mac_address: string
  interface: string
  vlan: string | null
  type: string | null
}

/** MAC 表条目 */
export interface MACEntry {
  mac_address: string
  vlan: string
  interface: string
  type: string | null
}

/** ARP 表响应 */
export interface ARPTableResponse {
  device_id: string
  device_name: string | null
  entries: ARPEntry[]
  collected_at: string
}

/** MAC 表响应 */
export interface MACTableResponse {
  device_id: string
  device_name: string | null
  entries: MACEntry[]
  collected_at: string
}

/** 设备采集结果 */
export interface DeviceCollectResult {
  device_id: string
  device_name: string | null
  arp_count: number
  mac_count: number
  collected_at: string
  error: string | null
}

/** 批量采集结果 */
export interface CollectResult {
  total: number
  success_count: number
  failed_count: number
  results: DeviceCollectResult[]
}

/** 采集任务状态 */
export interface CollectTaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE'
  progress: number | null
  result: CollectResult | null
  error: string | null
}

/** 定位响应 */
export interface LocateResponse {
  ip_address: string | null
  mac_address: string
  device_id: string | null
  device_name: string | null
  interface: string | null
  vlan: string | null
  located_at: string | null
}

/** 批量采集请求 */
export interface BatchCollectRequest {
  device_ids: string[]
  collect_arp?: boolean
  collect_mac?: boolean
  otp_code?: string
}

// ==================== API 函数 ====================

/** 手动采集单设备 */
export function collectDevice(deviceId: string) {
  return request<ResponseBase<DeviceCollectResult>>({
    url: `/collect/device/${deviceId}`,
    method: 'post',
    data: {},
  })
}

/** 批量采集设备 */
export function batchCollect(data: BatchCollectRequest) {
  return request<ResponseBase<CollectResult>>({
    url: '/collect/batch',
    method: 'post',
    data,
  })
}

/** 异步批量采集 */
export function batchCollectAsync(data: BatchCollectRequest) {
  return request<ResponseBase<CollectTaskStatus>>({
    url: '/collect/batch/async',
    method: 'post',
    data,
  })
}

/** 查询采集任务状态 */
export function getCollectTaskStatus(taskId: string) {
  return request<ResponseBase<CollectTaskStatus>>({
    url: `/collect/task/${taskId}`,
    method: 'get',
  })
}

/** 获取设备 ARP 表 */
export function getDeviceARPTable(deviceId: string) {
  return request<ResponseBase<ARPTableResponse>>({
    url: `/collect/device/${deviceId}/arp`,
    method: 'get',
  })
}

/** 获取设备 MAC 表 */
export function getDeviceMACTable(deviceId: string) {
  return request<ResponseBase<MACTableResponse>>({
    url: `/collect/device/${deviceId}/mac`,
    method: 'get',
  })
}

/** IP 地址定位 */
export function locateIP(ipAddress: string) {
  return request<ResponseBase<LocateResponse>>({
    url: `/collect/locate/ip/${encodeURIComponent(ipAddress)}`,
    method: 'get',
  })
}

/** MAC 地址定位 */
export function locateMAC(macAddress: string) {
  return request<ResponseBase<LocateResponse>>({
    url: `/collect/locate/mac/${encodeURIComponent(macAddress)}`,
    method: 'get',
  })
}
