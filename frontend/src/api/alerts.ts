/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: alerts.ts
 * @DateTime: 2026-01-10
 * @Docs: 告警管理 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

// ==================== 枚举类型 ====================

/** 告警类型 */
export type AlertType = 'device_offline' | 'config_change' | 'threshold' | 'security'

/** 告警级别 */
export type AlertSeverity = 'info' | 'warning' | 'critical'

/** 告警状态 */
export type AlertStatus = 'open' | 'acknowledged' | 'closed'

// ==================== 接口定义 ====================

/** 告警响应接口 */
export interface Alert {
  id: string
  title: string
  content: string | null
  alert_type: AlertType
  severity: AlertSeverity
  status: AlertStatus
  related_device_id: string | null
  related_device_name: string | null
  acknowledged_by: string | null
  acknowledged_at: string | null
  closed_by: string | null
  closed_at: string | null
  created_at: string
  updated_at: string | null
}

/** 告警查询参数 */
export interface AlertSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  alert_type?: AlertType
  severity?: AlertSeverity
  status?: AlertStatus
  related_device_id?: string
}

// ==================== API 函数 ====================

/** 获取告警列表 */
export function getAlerts(params?: AlertSearchParams) {
  return request<ResponseBase<PaginatedResponse<Alert>>>({
    url: '/alerts/',
    method: 'get',
    params,
  })
}

/** 获取告警详情 */
export function getAlert(id: string) {
  return request<ResponseBase<Alert>>({
    url: `/alerts/${id}`,
    method: 'get',
  })
}

/** 确认告警 */
export function acknowledgeAlert(id: string) {
  return request<ResponseBase<Alert>>({
    url: `/alerts/${id}/ack`,
    method: 'post',
  })
}

/** 关闭告警 */
export function closeAlert(id: string) {
  return request<ResponseBase<Alert>>({
    url: `/alerts/${id}/close`,
    method: 'post',
  })
}
