/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: topology.ts
 * @DateTime: 2026-01-10
 * @Docs: 网络拓扑 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

// ==================== 接口定义 ====================

/** 拓扑节点 */
export interface TopologyNode {
  id: string
  label: string
  title?: string
  group?: 'core' | 'distribution' | 'access' | 'unknown'
  shape: string
  size: number
  color?: string
  ip?: string
  vendor?: string
  device_group?: string
  in_cmdb: boolean
  // 兼容旧字段以防万一
  device_id?: string | null
  device_type?: string | null
  ip_address?: string | null
  status?: string | null
}

/** 拓扑边 */
export interface TopologyEdge {
  id?: string
  from: string
  to: string
  label?: string
  title?: string
  arrows: string
  source_interface?: string
  target_interface?: string
  link_type?: string
  // 兼容旧字段
  local_port?: string | null
  remote_port?: string | null
}

/** 拓扑统计 */
export interface TopologyStats {
  total_nodes: number
  total_edges: number
  cmdb_devices: number
  unknown_devices: number
  collected_at?: string
  cache_expires_at?: string
  device_types?: Record<string, number>
}

/** 拓扑响应 */
export interface TopologyResponse {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
  stats: TopologyStats
}

/** 拓扑链路响应 */
export interface TopologyLinkResponse {
  id: string
  source_device_id: string
  source_device_name: string | null
  source_port: string
  target_device_id: string
  target_device_name: string | null
  target_port: string
  link_type: string | null
  discovered_at: string
}

/** 设备邻居响应 */
export interface DeviceNeighborsResponse {
  device_id: string
  device_name: string | null
  neighbors: TopologyLinkResponse[]
  total: number
}

/** 拓扑采集请求 */
export interface TopologyCollectRequest {
  device_ids?: string[]
  async_mode?: boolean
}

/** 拓扑采集结果 */
export interface TopologyCollectResult {
  total_devices: number
  success_count: number
  failed_count: number
  new_links: number
}

/** 拓扑任务状态 */
export interface TopologyTaskStatus {
  task_id: string
  status: string
  progress: number | null
  result: TopologyCollectResult | null
  error: string | null
}

/** 拓扑任务响应 */
export interface TopologyTaskResponse {
  task_id: string
  status: string
  message: string
}

/** 拓扑链路列表响应 */
export interface TopologyLinksResponse {
  items: TopologyLinkItem[]
  total: number
  page: number
  page_size: number
}

/** 拓扑链路项 */
export interface TopologyLinkItem {
  id: string
  source_device_id: string
  source_interface: string
  target_device_id: string | null
  target_interface: string | null
  target_hostname: string | null
  target_ip: string | null
  link_type: string
  collected_at: string | null
}

// ==================== API 函数 ====================

/** 获取拓扑数据 */
export function getTopology() {
  return request<ResponseBase<TopologyResponse>>({
    url: '/topology/',
    method: 'get',
  })
}

/** 获取链路列表 */
export function getTopologyLinks(params?: { page?: number; page_size?: number }) {
  return request<ResponseBase<TopologyLinksResponse>>({
    url: '/topology/links',
    method: 'get',
    params,
  })
}

/** 获取设备邻居 */
export function getDeviceNeighbors(deviceId: string) {
  return request<ResponseBase<DeviceNeighborsResponse>>({
    url: `/topology/device/${deviceId}/neighbors`,
    method: 'get',
  })
}

/** 导出拓扑数据 */
export function exportTopology() {
  return request<Blob>({
    url: '/topology/export',
    method: 'get',
    responseType: 'blob',
  })
}

/** 刷新拓扑（全局采集） */
export function refreshTopology(data?: TopologyCollectRequest) {
  return request<ResponseBase<TopologyTaskResponse>>({
    url: '/topology/refresh',
    method: 'post',
    data: data || {},
  })
}

/** 采集单设备拓扑 */
export function collectDeviceTopology(deviceId: string, asyncMode: boolean = true) {
  return request<ResponseBase<TopologyTaskResponse>>({
    url: `/topology/device/${deviceId}/collect`,
    method: 'post',
    params: { async_mode: asyncMode },
  })
}

/** 查询拓扑任务状态 */
export function getTopologyTaskStatus(taskId: string) {
  return request<ResponseBase<TopologyTaskStatus>>({
    url: `/topology/task/${taskId}`,
    method: 'get',
  })
}

/** 重建拓扑缓存 */
export function rebuildTopologyCache() {
  return request<ResponseBase<TopologyTaskResponse>>({
    url: '/topology/cache/rebuild',
    method: 'post',
  })
}
