/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: depts.ts
 * @DateTime: 2026-01-08
 * @Docs: 部门管理 API
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

/**
 * 部门信息
 */
export interface Dept {
  id: string
  name: string
  code: string
  parent_id: string | null
  sort: number
  leader?: string
  phone?: string
  email?: string
  is_active: boolean
  created_at: string
  updated_at: string
  children?: Dept[]
}

/**
 * 创建部门参数
 */
export interface DeptCreate {
  name: string
  code: string
  parent_id?: string | null
  sort?: number
  leader?: string
  phone?: string
  email?: string
}

/**
 * 更新部门参数
 */
export interface DeptUpdate {
  name?: string
  code?: string
  parent_id?: string | null
  sort?: number
  leader?: string
  phone?: string
  email?: string
  is_active?: boolean
}

/**
 * 部门搜索参数
 */
export interface DeptSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  is_active?: boolean
}

/**
 * 批量操作结果
 */
export interface BatchOperationResult {
  success_count: number
  failed_ids?: string[]
}

/**
 * 获取部门树
 */
export function getDeptTree(isActive?: boolean) {
  return request<ResponseBase<Dept[]>>({
    url: '/depts/tree',
    method: 'get',
    params: isActive !== undefined ? { is_active: isActive } : undefined,
  })
}

/**
 * 获取部门列表（分页）
 */
export function getDepts(params?: DeptSearchParams) {
  return request<ResponseBase<PaginatedResponse<Dept>>>({
    url: '/depts/',
    method: 'get',
    params,
  })
}

/**
 * 创建部门
 */
export function createDept(data: DeptCreate) {
  return request<ResponseBase<Dept>>({
    url: '/depts/',
    method: 'post',
    data,
  })
}

/**
 * 更新部门
 */
export function updateDept(id: string, data: DeptUpdate) {
  return request<ResponseBase<Dept>>({
    url: `/depts/${id}`,
    method: 'put',
    data,
  })
}

/**
 * 删除部门
 */
export function deleteDept(id: string) {
  return request<ResponseBase<Dept>>({
    url: `/depts/${id}`,
    method: 'delete',
  })
}

/**
 * 批量删除部门
 */
export function batchDeleteDepts(ids: string[], hardDelete = false) {
  return request<ResponseBase<BatchOperationResult>>({
    url: '/depts/batch',
    method: 'delete',
    data: { ids, hard_delete: hardDelete },
  })
}

/**
 * 获取部门回收站列表
 */
export function getRecycleBinDepts(params?: DeptSearchParams) {
  return request<ResponseBase<PaginatedResponse<Dept>>>({
    url: '/depts/recycle-bin',
    method: 'get',
    params,
  })
}

/**
 * 恢复已删除部门
 */
export function restoreDept(id: string) {
  return request<ResponseBase<Dept>>({
    url: `/depts/${id}/restore`,
    method: 'post',
  })
}

/**
 * 批量恢复部门
 */
export function batchRestoreDepts(ids: string[]) {
  return request<ResponseBase<BatchOperationResult>>({
    url: '/depts/batch/restore',
    method: 'post',
    data: { ids },
  })
}

// ==================== 彻底删除 API ====================

/**
 * 彻底删除部门
 */
export function hardDeleteDept(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/depts/${id}/hard`,
    method: 'delete',
  })
}

/**
 * 批量彻底删除部门
 */
export function batchHardDeleteDepts(ids: string[]) {
  return request<ResponseBase<BatchOperationResult>>({
    url: '/depts/batch/hard',
    method: 'delete',
    data: { ids },
  })
}
