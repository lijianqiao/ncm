/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: inventory.ts
 * @DateTime: 2026-01-10
 * @Docs: 资产盘点 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

// ==================== 枚举类型 ====================

/** 盘点任务状态 */
export type InventoryAuditStatus = 'pending' | 'running' | 'success' | 'failed'

// ==================== 接口定义 ====================

/** 盘点范围 */
export interface InventoryAuditScope {
  subnets?: string[]
  dept_ids?: string[]
}

/** 盘点统计 */
export interface InventoryAuditStats {
  total_scanned: number
  online_count: number
  offline_count: number
  shadow_count: number
  matched_count: number
  config_diff_count: number
}

/** 盘点响应 */
export interface InventoryAudit {
  id: string
  name: string
  scope: InventoryAuditScope
  status: InventoryAuditStatus
  celery_task_id: string | null
  stats: InventoryAuditStats | null
  created_by: string | null
  created_by_name: string | null
  created_at: string
  completed_at: string | null
  error: string | null
}

/** 创建盘点任务参数 */
export interface InventoryAuditCreate {
  name: string
  scope: InventoryAuditScope
}

/** 盘点任务查询参数 */
export interface InventoryAuditSearchParams {
  page?: number
  page_size?: number
  status?: InventoryAuditStatus
}

/** 盘点报告详情 */
export interface InventoryAuditReport {
  audit: InventoryAudit
  online_devices: Array<{ device_id: string; device_name: string; ip_address: string }>
  offline_devices: Array<{ device_id: string; device_name: string; ip_address: string; offline_days: number }>
  shadow_assets: Array<{ ip_address: string; mac_address: string | null; vendor: string | null }>
  config_diff_devices: Array<{ device_id: string; device_name: string; last_backup_at: string | null }>
}

// ==================== API 函数 ====================

/** 创建盘点任务 */
export function createInventoryAudit(data: InventoryAuditCreate) {
  return request<ResponseBase<InventoryAudit>>({
    url: '/inventory_audit/',
    method: 'post',
    data,
  })
}

/** 获取盘点任务列表 */
export function getInventoryAudits(params?: InventoryAuditSearchParams) {
  return request<ResponseBase<PaginatedResponse<InventoryAudit>>>({
    url: '/inventory_audit/',
    method: 'get',
    params,
  })
}

/** 获取盘点任务详情 */
export function getInventoryAudit(id: string) {
  return request<ResponseBase<InventoryAudit>>({
    url: `/inventory_audit/${id}`,
    method: 'get',
  })
}

/** 导出盘点报告 */
export function exportInventoryAudit(id: string) {
  return request<ResponseBase<InventoryAuditReport>>({
    url: `/inventory_audit/${id}/export`,
    method: 'get',
  })
}
