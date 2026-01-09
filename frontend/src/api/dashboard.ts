import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

export interface DashboardStats {
  total_users?: number
  active_users?: number
  total_roles?: number
  total_menus?: number
  today_login_count?: number
  today_operation_count?: number
  login_trend?: Array<{ date: string; count: number }>
  recent_logins?: Array<{
    id: string
    username: string
    ip: string
    browser: string
    os: string
    status: boolean
    created_at: string
  }>

  // Personal Stats
  my_today_login_count: number
  my_today_operation_count: number
  my_login_trend: Array<{ date: string; count: number }>
  my_recent_logins: Array<{
    id: string
    username: string
    ip: string
    browser: string
    os: string
    status: boolean
    created_at: string
  }>
}

export function getDashboardStats() {
  return request<ResponseBase<DashboardStats>>({
    url: '/dashboard/summary',
    method: 'get',
  })
}
