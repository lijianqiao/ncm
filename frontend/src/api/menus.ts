import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

export interface Menu {
  id: string
  parent_id: string | null
  title: string
  name: string // route name
  path: string // route path
  component: string | null // component path
  icon: string | null
  sort: number
  type: 'CATALOG' | 'MENU' | 'PERMISSION'
  permission: string | null
  is_hidden: boolean
  is_active: boolean
  created_at: string
  updated_at?: string | null
  children?: Menu[]
}

export interface MenuCreate {
  parent_id?: string | null
  title: string
  name: string
  path: string
  component?: string | null
  icon?: string | null
  sort?: number
  type: 'CATALOG' | 'MENU' | 'PERMISSION'
  permission?: string | null
  is_hidden?: boolean
  is_active?: boolean
}

export type MenuUpdate = Partial<MenuCreate>

export interface MenuSearchParams {
  page?: number
  page_size?: number
  keyword?: string
  is_active?: boolean
  is_hidden?: boolean
  type?: 'CATALOG' | 'MENU' | 'PERMISSION'
}

export function getMenus(params?: MenuSearchParams) {
  return request<ResponseBase<PaginatedResponse<Menu>>>({
    url: '/menus/',
    method: 'get',
    params,
  })
}

export function getRecycleBinMenus(params?: MenuSearchParams) {
  return request<ResponseBase<PaginatedResponse<Menu>>>({
    url: '/menus/recycle-bin',
    method: 'get',
    params,
  })
}

export function restoreMenu(id: string) {
  return request<ResponseBase<Menu>>({
    url: `/menus/${id}/restore`,
    method: 'post',
  })
}

export function createMenu(data: MenuCreate) {
  return request<ResponseBase<Menu>>({
    url: '/menus/',
    method: 'post',
    data,
  })
}

export function updateMenu(id: string, data: MenuUpdate) {
  return request<ResponseBase<Menu>>({
    url: `/menus/${id}`,
    method: 'put',
    data,
  })
}

export function deleteMenu(id: string) {
  return request<ResponseBase<unknown>>({
    url: `/menus/${id}`,
    method: 'delete',
  })
}

export function batchDeleteMenus(ids: string[], hard_delete: boolean = false) {
  return request<ResponseBase<unknown>>({
    url: '/menus/batch',
    method: 'delete',
    data: { ids, hard_delete },
  })
}

export function batchRestoreMenus(ids: string[]) {
  return request<ResponseBase<unknown>>({
    url: '/menus/batch/restore',
    method: 'post',
    data: { ids },
  })
}

// 侧边栏菜单（当前用户可见）
export function getMyMenus() {
  return request<ResponseBase<Menu[]>>({
    url: '/menus/me',
    method: 'get',
  })
}

// 角色分配权限用的菜单树选项
export function getMenuOptions() {
  return request<ResponseBase<Menu[]>>({
    url: '/menus/options',
    method: 'get',
  })
}
