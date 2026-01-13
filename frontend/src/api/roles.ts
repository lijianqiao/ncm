import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

export interface Role {
  id: string
  name: string
  code: string
  description: string | null
  is_active: boolean
  sort: number
  created_at: string
  updated_at: string | null
  menu_ids?: string[]
}

export interface RoleCreate {
  name: string
  code: string
  description?: string
  sort?: number
  is_active?: boolean
  menu_ids?: string[]
}

export type RoleUpdate = Partial<RoleCreate>

export interface RoleSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  is_active?: boolean
}

export function getRoles(params?: RoleSearchParams) {
  return request<ResponseBase<PaginatedResponse<Role>>>({
    url: '/roles/',
    method: 'get',
    params,
  })
}

/**
 * 获取角色选项列表（用于下拉选择等场景）
 * 返回完整的角色列表，不分页
 */
export function getRoleOptions() {
  return request<ResponseBase<PaginatedResponse<Role>>>({
    url: '/roles/',
    method: 'get',
    params: { page_size: 500 }, // 获取足够多的角色用于选择
  })
}

export function createRole(data: RoleCreate) {
  return request<ResponseBase<Role>>({
    url: '/roles/',
    method: 'post',
    data,
  })
}

export function updateRole(id: string, data: RoleUpdate) {
  return request<ResponseBase<Role>>({
    url: `/roles/${id}`,
    method: 'put',
    data,
  })
}

export function deleteRole(id: string) {
  return request<ResponseBase<unknown>>({
    url: `/roles/${id}`,
    method: 'delete',
  })
}

// Permission related APIs
export function getRoleMenus(roleId: string) {
  // Returns list of menu IDs (array of strings)
  return request<ResponseBase<string[]>>({
    url: `/roles/${roleId}/menus`,
    method: 'get',
  })
}

export function updateRoleMenus(roleId: string, menuIds: string[]) {
  // Sets role menus
  return request<ResponseBase<string[]>>({
    url: `/roles/${roleId}/menus`,
    method: 'put',
    data: { menu_ids: menuIds },
  })
}

export function batchDeleteRoles(ids: string[], hard_delete: boolean = false) {
  return request<ResponseBase<unknown>>({
    url: '/roles/batch',
    method: 'delete',
    data: { ids, hard_delete },
  })
}

export function batchRestoreRoles(ids: string[]) {
  return request<ResponseBase<unknown>>({
    url: '/roles/batch/restore',
    method: 'post',
    data: { ids },
  })
}

export function getRecycleBinRoles(params?: RoleSearchParams) {
  return request<ResponseBase<PaginatedResponse<Role>>>({
    url: '/roles/recycle-bin',
    method: 'get',
    params,
  })
}

export function restoreRole(id: string) {
  return request<ResponseBase<Role>>({
    url: `/roles/${id}/restore`,
    method: 'post',
  })
}
