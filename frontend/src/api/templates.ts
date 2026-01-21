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
import type { TemplateTypeType, TemplateStatusType, DeviceTypeType } from '@/types/enums'
import type { AxiosResponse } from 'axios'

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
  approvals?: Array<{
    level: number
    approver_id: string | null
    approver_name: string | null
    status: 'pending' | 'approved' | 'rejected'
    comment: string | null
    approved_at: string | null
  }>
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
  approver_ids?: string[]
}

/** 审批请求 */
export interface TemplateApproveRequest {
  level: number
  approve: boolean
  comment?: string
}

/** 模板渲染请求 */
export interface RenderRequest {
  params?: Record<string, unknown>
  variables?: Record<string, unknown>
  device_id?: string
}

/** 模板渲染响应 */
export interface RenderResponse {
  rendered: string
}

/** 渲染模板 (预览) */
export function previewTemplateRender(id: string, data: RenderRequest) {
  return request<ResponseBase<RenderResponse>>({
    url: `/templates/${id}/render`,
    method: 'post',
    data,
  })
}

// ==================== V2 接口定义 ====================

/** 模板参数定义 (V2) */
export interface TemplateParameterCreate {
  name: string
  label?: string
  param_type: string
  required?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default_value?: any
  description?: string
  options?: string[]
  min_value?: number
  max_value?: number
  pattern?: string
  order?: number
}

/** 创建模板参数 (V2) */
export interface TemplateCreateV2 {
  name: string
  description?: string
  template_type?: TemplateTypeType
  content: string
  vendors: DeviceVendor[]
  device_type?: DeviceTypeType
  parameters_list?: TemplateParameterCreate[]
}

/** 更新模板参数 (V2) */
export interface TemplateUpdateV2 {
  name?: string
  description?: string
  template_type?: TemplateTypeType
  content?: string
  vendors?: DeviceVendor[]
  device_type?: DeviceTypeType
  parameters_list?: TemplateParameterCreate[]
  status?: TemplateStatusType
}

/** 模板响应接口 (V2) */
export interface TemplateResponseV2 extends Template {
  parameters_list?: TemplateParameterCreate[]
}

/** 参数类型定义 */
export interface TemplateParamType {
  value: string
  label: string
  has_options?: boolean
  has_range?: boolean
  has_pattern?: boolean
}

/** 示例模板响应 */
export interface TemplateExample {
  id: string
  name: string
  description: string
  template_type: TemplateTypeType
  content: string
  parameters: TemplateParameterCreate[]
}

// ==================== API 函数 ====================

/** 获取示例模板列表 */
export function getTemplateExamples() {
  return request<ResponseBase<{ examples: TemplateExample[] }>>({
    url: '/templates/examples',
    method: 'get',
  })
}

/** 获取模板列表 */
export function getTemplates(params?: TemplateSearchParams) {
  return request<ResponseBase<PaginatedResponse<Template>>>({
    url: '/templates/',
    method: 'get',
    params,
  })
}

/** 获取模板详情 */
export function getTemplate(id: string) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}`,
    method: 'get',
  })
}

/** 创建模板 */
export function createTemplate(data: TemplateCreate) {
  return request<ResponseBase<Template>>({
    url: '/templates/',
    method: 'post',
    data,
  })
}

/** 更新模板 */
export function updateTemplate(id: string, data: TemplateUpdate) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}`,
    method: 'put',
    data,
  })
}

/** 删除模板 */
export function deleteTemplate(id: string) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}`,
    method: 'delete',
  })
}

/** 创建新版本 */
export function createTemplateVersion(id: string, data?: TemplateNewVersionRequest) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}/new-version`,
    method: 'post',
    data: data || {},
  })
}

/** 提交模板审批 */
export function submitTemplate(id: string, data?: TemplateSubmitRequest) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}/submit`,
    method: 'post',
    data: data || {},
  })
}

/** 审批模板（三级审批） */
export function approveTemplate(id: string, data: TemplateApproveRequest) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}/approve`,
    method: 'post',
    data,
  })
}

// ==================== V2 API 函数 ====================

/** 获取参数类型列表 */
export function getParamTypes() {
  return request<ResponseBase<TemplateParamType[]>>({
    url: '/templates/param-types',
    method: 'get',
  })
}

/** 提取模板变量 */
export function extractTemplateVars(content: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return request<ResponseBase<{ variables: Array<string | any> }>>({
    url: '/templates/extract-vars',
    method: 'post',
    data: { content },
  })
}

/** 创建模板 (V2) */
export function createTemplateV2(data: TemplateCreateV2) {
  return request<ResponseBase<TemplateResponseV2>>({
    url: '/templates/v2',
    method: 'post',
    data,
  })
}

/** 更新模板 (V2) */
export function updateTemplateV2(id: string, data: TemplateUpdateV2) {
  return request<ResponseBase<TemplateResponseV2>>({
    url: `/templates/v2/${id}`,
    method: 'put',
    data,
  })
}

/** 获取模板详情 (V2) */
export function getTemplateV2(id: string) {
  return request<ResponseBase<TemplateResponseV2>>({
    url: `/templates/v2/${id}`,
    method: 'get',
  })
}

// ==================== 批量操作和回收站 API ====================

/** 批量操作结果 */
export interface TemplateBatchResult {
  success_count: number
  failed_count: number
  failed_ids: string[]
}

/** 批量删除模板 */
export function batchDeleteTemplates(ids: string[]) {
  return request<ResponseBase<TemplateBatchResult>>({
    url: '/templates/batch',
    method: 'delete',
    data: { ids },
  })
}

/** 获取回收站模板列表 */
export function getRecycleBinTemplates(params?: {
  page?: number
  page_size?: number
  keyword?: string
}) {
  return request<ResponseBase<PaginatedResponse<Template>>>({
    url: '/templates/recycle-bin',
    method: 'get',
    params,
  })
}

/** 恢复模板 */
export function restoreTemplate(id: string) {
  return request<ResponseBase<Template>>({
    url: `/templates/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复模板 */
export function batchRestoreTemplates(ids: string[]) {
  return request<ResponseBase<TemplateBatchResult>>({
    url: '/templates/batch/restore',
    method: 'post',
    data: { ids },
  })
}

/** 彻底删除模板 */
export function hardDeleteTemplate(id: string) {
  return request<ResponseBase<Record<string, unknown>>>({
    url: `/templates/${id}/hard`,
    method: 'delete',
  })
}

/** 批量彻底删除模板 */
export function batchHardDeleteTemplates(ids: string[]) {
  return request<ResponseBase<TemplateBatchResult>>({
    url: '/templates/batch/hard',
    method: 'delete',
    data: { ids },
  })
}

export function exportTemplates(fmt: 'csv' | 'xlsx' = 'csv') {
  return request<AxiosResponse<Blob>>({
    url: '/templates/export',
    method: 'get',
    params: { fmt },
    responseType: 'blob',
  })
}
