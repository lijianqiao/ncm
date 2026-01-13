import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type { Role } from '@/api/roles'

export interface User {
  id: string
  username: string
  email: string | null
  phone: string | null
  nickname: string | null
  gender: string | null
  is_active: boolean
  is_superuser: boolean
  dept_id: string | null
  dept_name: string | null
  created_at: string
  updated_at: string | null
  permissions?: string[]
  roles?: string[] // Role codes or names
}

export interface UserCreate {
  username: string
  password: string
  email?: string
  phone: string
  nickname?: string
  gender?: string
  is_active?: boolean
  is_superuser?: boolean
  dept_id?: string | null
}

export type UserUpdate = Partial<UserCreate>

export interface UserSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  is_active?: boolean
  is_superuser?: boolean
}

export function getUsers(params?: UserSearchParams) {
  return request<ResponseBase<PaginatedResponse<User>>>({
    url: '/users/',
    method: 'get',
    params,
  })
}

export function createUser(data: UserCreate) {
  return request<ResponseBase<User>>({
    url: '/users/',
    method: 'post',
    data,
  })
}

export function updateUser(id: string | number, data: UserUpdate) {
  return request<ResponseBase<User>>({
    url: `/users/${id}`,
    method: 'put',
    data,
  })
}

// User Role Assignment
export function getUserRoles(userId: string) {
  // 返回用户角色列表
  return request<ResponseBase<Role[]>>({
    url: `/users/${userId}/roles`,
    method: 'get',
  })
}

export function updateUserRoles(userId: string, roleIds: string[]) {
  return request<ResponseBase<Role[]>>({
    url: `/users/${userId}/roles`,
    method: 'put',
    data: { role_ids: roleIds },
  })
}

export function batchDeleteUsers(ids: string[], hard_delete: boolean = false) {
  return request<ResponseBase<unknown>>({
    url: '/users/batch',
    method: 'delete',
    data: { ids, hard_delete },
  })
}

export function batchRestoreUsers(ids: string[]) {
  return request<ResponseBase<unknown>>({
    url: '/users/batch/restore',
    method: 'post',
    data: { ids },
  })
}

export function getRecycleBinUsers(params?: UserSearchParams) {
  return request<ResponseBase<PaginatedResponse<User>>>({
    url: '/users/recycle-bin',
    method: 'get',
    params,
  })
}

export function restoreUser(id: string) {
  return request<ResponseBase<User>>({
    url: `/users/${id}/restore`,
    method: 'post',
  })
}

export function resetUserPassword(userId: string, newPassword: string) {
  return request<ResponseBase<User>>({
    url: `/users/${userId}/password`,
    method: 'put',
    data: { new_password: newPassword },
  })
}
