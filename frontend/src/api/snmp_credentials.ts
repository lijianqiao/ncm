/**
 * @Author: li
 * @Email: li
 * @FileName: snmp_credentials.ts
 * @DateTime: 2026-01-14
 * @Docs: 部门 SNMP 凭据 API 模块
 */

import { request } from '@/utils/request'
import type { PaginatedResponse, ResponseBase } from '@/types/api'

export type SnmpVersion = 'v2c' | 'v3'

export interface DeptSnmpCredential {
  id: string
  dept_id: string
  dept_name: string | null
  snmp_version: SnmpVersion
  port: number
  has_community: boolean
  description: string | null
  created_at: string
  updated_at: string | null
}

export interface DeptSnmpCredentialCreate {
  dept_id: string
  snmp_version?: SnmpVersion
  port?: number
  community?: string
  v3_username?: string
  v3_auth_key?: string
  v3_priv_key?: string
  v3_auth_proto?: string
  v3_priv_proto?: string
  v3_security_level?: string
  description?: string
}

export interface DeptSnmpCredentialUpdate {
  snmp_version?: SnmpVersion
  port?: number
  community?: string | null
  v3_username?: string | null
  v3_auth_key?: string | null
  v3_priv_key?: string | null
  v3_auth_proto?: string | null
  v3_priv_proto?: string | null
  v3_security_level?: string | null
  description?: string | null
}

export interface SnmpCredentialSearchParams {
  page?: number
  page_size?: number
  dept_id?: string
}

export function getSnmpCredentials(params?: SnmpCredentialSearchParams) {
  return request<ResponseBase<PaginatedResponse<DeptSnmpCredential>>>({
    url: '/snmp_credentials/',
    method: 'get',
    params,
  })
}

export function createSnmpCredential(data: DeptSnmpCredentialCreate) {
  return request<ResponseBase<DeptSnmpCredential>>({
    url: '/snmp_credentials/',
    method: 'post',
    data,
  })
}

export function updateSnmpCredential(id: string, data: DeptSnmpCredentialUpdate) {
  return request<ResponseBase<DeptSnmpCredential>>({
    url: `/snmp_credentials/${id}`,
    method: 'put',
    data,
  })
}

export function deleteSnmpCredential(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/snmp_credentials/${id}`,
    method: 'delete',
  })
}

// ==================== 批量操作和回收站 API ====================

/** 批量操作结果 */
export interface SnmpCredentialBatchResult {
  success_count: number
  failed_count: number
  failed_ids: string[]
}

/** 批量删除 SNMP 凭据 */
export function batchDeleteSnmpCredentials(ids: string[]) {
  return request<ResponseBase<SnmpCredentialBatchResult>>({
    url: '/snmp_credentials/batch',
    method: 'delete',
    data: { ids },
  })
}

/** 获取回收站 SNMP 凭据列表 */
export function getRecycleBinSnmpCredentials(params?: { page?: number; page_size?: number; keyword?: string }) {
  return request<ResponseBase<PaginatedResponse<DeptSnmpCredential>>>({
    url: '/snmp_credentials/recycle-bin',
    method: 'get',
    params,
  })
}

/** 恢复 SNMP 凭据 */
export function restoreSnmpCredential(id: string) {
  return request<ResponseBase<DeptSnmpCredential>>({
    url: `/snmp_credentials/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复 SNMP 凭据 */
export function batchRestoreSnmpCredentials(ids: string[]) {
  return request<ResponseBase<SnmpCredentialBatchResult>>({
    url: '/snmp_credentials/batch/restore',
    method: 'post',
    data: { ids },
  })
}

/** 彻底删除 SNMP 凭据 */
export function hardDeleteSnmpCredential(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/snmp_credentials/${id}/hard`,
    method: 'delete',
  })
}

/** 批量彻底删除 SNMP 凭据 */
export function batchHardDeleteSnmpCredentials(ids: string[]) {
  return request<ResponseBase<SnmpCredentialBatchResult>>({
    url: '/snmp_credentials/batch/hard',
    method: 'delete',
    data: { ids },
  })
}