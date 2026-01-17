/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: credentials.ts
 * @DateTime: 2026-01-10
 * @Docs: 凭据管理 API 模块
 */

import { request } from '@/utils/request'
import type {
  ResponseBase,
  PaginatedResponse,
  ImportValidateResponse,
  ImportPreviewResponse,
  ImportCommitRequest,
  ImportCommitResponse,
} from '@/types/api'
import type { DeviceGroup, AuthType } from './devices'
import type { AxiosResponse } from 'axios'

// ==================== 接口定义 ====================

/** 凭据响应接口 */
export interface Credential {
  id: string
  dept_id: string
  dept_name: string | null
  device_group: DeviceGroup
  username: string
  auth_type: AuthType
  description: string | null
  has_otp_seed: boolean
  created_at: string
  updated_at: string | null
}

/** 创建凭据参数 */
export interface CredentialCreate {
  dept_id: string
  device_group: DeviceGroup
  username: string
  otp_seed?: string
  auth_type?: AuthType
  description?: string
}

/** 更新凭据参数 */
export interface CredentialUpdate {
  username?: string
  otp_seed?: string
  auth_type?: AuthType
  description?: string
}

/** 凭据查询参数 */
export interface CredentialSearchParams {
  page?: number
  page_size?: number
  dept_id?: string
  device_group?: DeviceGroup
}

/** OTP 缓存请求 */
export interface OTPCacheRequest {
  dept_id: string
  device_group: DeviceGroup
  otp_code: string
}

/** OTP 缓存响应 */
export interface OTPCacheResponse {
  success: boolean
  message: string
  expires_in: number
}

// ==================== API 函数 ====================

/** 获取凭据列表 */
export function getCredentials(params?: CredentialSearchParams) {
  return request<ResponseBase<PaginatedResponse<Credential>>>({
    url: '/credentials/',
    method: 'get',
    params,
  })
}

/** 获取凭据详情 */
export function getCredential(id: string) {
  return request<ResponseBase<Credential>>({
    url: `/credentials/${id}`,
    method: 'get',
  })
}

/** 创建凭据 */
export function createCredential(data: CredentialCreate) {
  return request<ResponseBase<Credential>>({
    url: '/credentials/',
    method: 'post',
    data,
  })
}

/** 更新凭据 */
export function updateCredential(id: string, data: CredentialUpdate) {
  return request<ResponseBase<Credential>>({
    url: `/credentials/${id}`,
    method: 'put',
    data,
  })
}

/** 删除凭据 */
export function deleteCredential(id: string) {
  return request<ResponseBase<Credential>>({
    url: `/credentials/${id}`,
    method: 'delete',
  })
}

/** 缓存 OTP 验证码 */
export function cacheOTP(data: OTPCacheRequest) {
  return request<ResponseBase<OTPCacheResponse>>({
    url: '/credentials/otp/cache',
    method: 'post',
    data,
  })
}

// ==================== 批量操作和回收站 API ====================

/** 批量操作结果 */
export interface CredentialBatchResult {
  success_count: number
  failed_count: number
  failed_ids: string[]
}

/** 批量删除凭据 */
export function batchDeleteCredentials(ids: string[]) {
  return request<ResponseBase<CredentialBatchResult>>({
    url: '/credentials/batch',
    method: 'delete',
    data: { ids },
  })
}

/** 获取回收站凭据列表 */
export function getRecycleBinCredentials(params?: { page?: number; page_size?: number; keyword?: string }) {
  return request<ResponseBase<PaginatedResponse<Credential>>>({
    url: '/credentials/recycle-bin',
    method: 'get',
    params,
  })
}

/** 恢复凭据 */
export function restoreCredential(id: string) {
  return request<ResponseBase<Credential>>({
    url: `/credentials/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复凭据 */
export function batchRestoreCredentials(ids: string[]) {
  return request<ResponseBase<CredentialBatchResult>>({
    url: '/credentials/batch/restore',
    method: 'post',
    data: { ids },
  })
}

/** 彻底删除凭据 */
export function hardDeleteCredential(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/credentials/${id}/hard`,
    method: 'delete',
  })
}

/** 批量彻底删除凭据 */
export function batchHardDeleteCredentials(ids: string[]) {
  return request<ResponseBase<CredentialBatchResult>>({
    url: '/credentials/batch/hard',
    method: 'delete',
    data: { ids },
  })
}

// ==================== 导入导出 API ====================

export function exportCredentials(fmt: 'csv' | 'xlsx' = 'csv') {
  return request<AxiosResponse<Blob>>({
    url: '/credentials/export',
    method: 'get',
    params: { fmt },
    responseType: 'blob',
  })
}

export function downloadCredentialImportTemplate() {
  return request<AxiosResponse<Blob>>({
    url: '/credentials/import/template',
    method: 'get',
    responseType: 'blob',
  })
}

export function uploadCredentialImportFile(file: File, allowOverwrite = false) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('allow_overwrite', allowOverwrite ? 'true' : 'false')
  return request<ResponseBase<ImportValidateResponse>>({
    url: '/credentials/import/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function previewCredentialImport(params: {
  import_id: string
  checksum: string
  page?: number
  page_size?: number
}) {
  return request<ResponseBase<ImportPreviewResponse>>({
    url: '/credentials/import/preview',
    method: 'get',
    params,
  })
}

export function commitCredentialImport(data: ImportCommitRequest) {
  return request<ResponseBase<ImportCommitResponse>>({
    url: '/credentials/import/commit',
    method: 'post',
    data,
  })
}
