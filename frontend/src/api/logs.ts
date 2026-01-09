import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

export interface LoginLog {
  id: string
  user_id: string
  username: string
  ip: string
  user_agent: string
  browser: string
  os: string
  device: string
  status: boolean
  msg: string
  created_at: string
}

export interface OperationLog {
  id: string
  user_id: string
  username: string
  ip: string
  module: string
  summary: string
  method: string
  path: string
  params?: Record<string, unknown> | null
  response_result?: Record<string, unknown> | null
  user_agent?: string
  response_code: number
  duration: number
  created_at: string
}

export interface LogSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  sort?: string
}

export function getLoginLogs(params?: LogSearchParams) {
  return request<ResponseBase<PaginatedResponse<LoginLog>>>({
    url: '/logs/login',
    method: 'get',
    params,
  })
}

export function getOperationLogs(params?: LogSearchParams) {
  return request<ResponseBase<PaginatedResponse<OperationLog>>>({
    url: '/logs/operation',
    method: 'get',
    params,
  })
}
