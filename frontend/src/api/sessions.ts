/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: sessions.ts
 * @DateTime: 2026-01-08
 * @Docs: 在线会话管理 API
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type { AxiosResponse } from 'axios'

/**
 * 在线会话信息
 */
export interface OnlineSession {
  user_id: string
  username: string
  ip: string
  user_agent: string
  login_at: string
  last_seen_at: string
}

/**
 * 会话搜索参数
 */
export interface SessionSearchParams {
  page?: number
  page_size?: number
  keyword?: string
}

/**
 * 批量踢人请求
 */
export interface KickUsersRequest {
  user_ids: string[]
}

/**
 * 批量操作结果
 */
export interface BatchOperationResult {
  success_count: number
  failed_ids?: string[]
}

/**
 * 获取在线会话列表
 * 需要 SESSION_LIST 权限
 */
export function getOnlineSessions(params?: SessionSearchParams) {
  return request<ResponseBase<PaginatedResponse<OnlineSession>>>({
    url: '/sessions/online',
    method: 'get',
    params,
  })
}

/**
 * 强制下线指定用户（踢人）
 * 需要 SESSION_KICK 权限
 */
export function kickUser(userId: string) {
  return request<ResponseBase<void>>({
    url: `/sessions/kick/${userId}`,
    method: 'post',
  })
}

/**
 * 批量强制下线
 * 需要 SESSION_KICK 权限
 */
export function batchKickUsers(userIds: string[]) {
  return request<ResponseBase<BatchOperationResult>>({
    url: '/sessions/kick/batch',
    method: 'post',
    data: { user_ids: userIds },
  })
}

export function exportSessions(fmt: 'csv' | 'xlsx' = 'csv') {
  return request<AxiosResponse<Blob>>({
    url: '/sessions/export',
    method: 'get',
    params: { fmt },
    responseType: 'blob',
  })
}
