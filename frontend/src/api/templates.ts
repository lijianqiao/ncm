/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: templates.ts
 * @DateTime: 2026-01-10
 * @Docs: 模板管理 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'
import type { DeviceVendor } from './devices'
import type {
  TemplateTypeType,
  TemplateStatusType,
  DeviceTypeType,
} from '@/types/enums'

// 重新导出枚举类型供外部使用
export type { TemplateTypeType as TemplateType }
export type { TemplateStatusType as TemplateStatus }
export type { DeviceTypeType as DeviceType }

// ==================== 接口定义 ====================

/** 模板响应接口 */
export interface Template {
  id: string
  name: string
  description: string | null
  template_type: TemplateTypeType
  content: string
  vendors: DeviceVendor[]
  device_type: DeviceTypeType | null
  parameters: string | null
  status: TemplateStatusType
  version: number
  parent_id: string | null
  created_by: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string | null
}

/** 创建模板参数 */
export interface TemplateCreate {
  name: string
  description?: string
  template_type?: TemplateTypeType
  content: string
  vendors: DeviceVendor[]
  device_type?: DeviceTypeType
  parameters?: string
}

/** 更新模板参数 */
export interface TemplateUpdate {
  name?: string
  description?: string
  template_type?: TemplateTypeType
  content?: string
  vendors?: DeviceVendor[]
  device_type?: DeviceTypeType
  parameters?: string
  status?: TemplateStatusType
}

/** 模板查询参数 */
export interface TemplateSearchParams {
  page?: number
  page_size?: number
  vendor?: DeviceVendor
  template_type?: TemplateTypeType
  status?: TemplateStatusType
}

/** 新版本请求 */
export interface TemplateNewVersionRequest {
  name?: string
  description?: string
}

/** 提交审批请求 */
export interface TemplateSubmitRequest {
  comment?: string
}

// ==================== API 函数 ====================

/** 获取模板列表 */
export function getTemplates(params?: TemplateSearchParams) {
  return request<ResponseBase<PaginatedResponse<Template>>>({
    url: '/templates/templates/',
    method: 'get',
    params,
  })
}

/** 获取模板详情 */
export function getTemplate(id: string) {
  return request<ResponseBase<Template>>({
    url: `/templates/templates/${id}`,
    method: 'get',
  })
}

/** 创建模板 */
export function createTemplate(data: TemplateCreate) {
  return request<ResponseBase<Template>>({
    url: '/templates/templates/',
    method: 'post',
    data,
  })
}

/** 更新模板 */
export function updateTemplate(id: string, data: TemplateUpdate) {
  return request<ResponseBase<Template>>({
    url: `/templates/templates/${id}`,
    method: 'put',
    data,
  })
}

/** 删除模板 */
export function deleteTemplate(id: string) {
  return request<ResponseBase<Template>>({
    url: `/templates/templates/${id}`,
    method: 'delete',
  })
}

/** 创建新版本 */
export function createTemplateVersion(id: string, data?: TemplateNewVersionRequest) {
  return request<ResponseBase<Template>>({
    url: `/templates/templates/${id}/new-version`,
    method: 'post',
    data: data || {},
  })
}

/** 提交模板审批 */
export function submitTemplate(id: string, data?: TemplateSubmitRequest) {
  return request<ResponseBase<Template>>({
    url: `/templates/templates/${id}/submit`,
    method: 'post',
    data: data || {},
  })
}
