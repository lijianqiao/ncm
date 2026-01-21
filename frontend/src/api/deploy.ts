/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: deploy.ts
 * @DateTime: 2026-01-10
 * @Docs: 配置下发 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

// ==================== 枚举类型 ====================

/** 下发任务状态 */
export type DeployTaskStatus =
  | 'pending'
  | 'approving'
  | 'approved'
  | 'rejected'
  | 'running'
  | 'executing'
  | 'success'
  | 'failed'
  | 'partial'
  | 'paused'
  | 'cancelled'
  | 'rollback'

// ==================== 接口定义 ====================

/** 下发计划 */
export interface DeployPlan {
  scheduled_at?: string
  execute_mode?: 'serial' | 'parallel'
  batch_size?: number
  concurrency?: number
  strict_allowlist?: boolean
  dry_run?: boolean
}

/** 审批记录 */
export interface ApprovalRecord {
  level: number
  approver_id: string | null
  approver_name: string | null
  status: 'pending' | 'approved' | 'rejected'
  comment: string | null
  approved_at: string | null
}

/** 设备执行结果 */
export interface DeviceDeployResult {
  device_id: string
  device_name: string | null
  status: 'pending' | 'success' | 'failed'
  output: string | null
  error: string | null
  executed_at: string | null
}

/** 下发任务响应 */
export interface DeployTask {
  id: string
  name: string
  task_type?: string
  description: string | null
  template_id: string
  template_name?: string | null
  template_params: Record<string, unknown> | null
  rendered_content?: string | null
  device_ids?: string[]
  target_devices?: {
    device_ids: string[]
  } | null
  total_devices?: number
  success_count?: number
  failed_count?: number
  status: DeployTaskStatus
  approval_status?: 'pending' | 'approved' | 'rejected' | string
  current_approval_level?: number
  change_description: string | null
  impact_scope: string | null
  rollback_plan: string | null
  deploy_plan: DeployPlan | null
  approvals?: ApprovalRecord[]
  device_results?: DeviceDeployResult[]
  celery_task_id: string | null
  created_by: string | null
  created_by_name?: string | null
  created_at: string
  updated_at: string | null
  result?: unknown
  error_message?: string | null
}

/** 创建下发任务参数 */
export interface DeployCreateRequest {
  name: string
  description?: string
  template_id: string
  template_params?: Record<string, unknown>
  device_ids: string[]
  change_description?: string
  impact_scope?: string
  rollback_plan?: string
  approver_ids?: string[]
  deploy_plan?: DeployPlan
}

/** 审批请求 */
export interface DeployApproveRequest {
  level: number
  approve: boolean
  comment?: string
}

/** 回滚响应 */
export interface DeployRollbackResponse {
  task_id: string
  rollback_task_id: string
}

/** 下发任务查询参数 */
export interface DeploySearchParams {
  page?: number
  page_size?: number
  status?: DeployTaskStatus
}

// ==================== API 函数 ====================

/** 获取下发任务列表 */
export function getDeployTasks(params?: DeploySearchParams) {
  return request<ResponseBase<PaginatedResponse<DeployTask>>>({
    url: '/deploy/',
    method: 'get',
    params,
  })
}

/** 获取下发任务详情 */
export function getDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}`,
    method: 'get',
  })
}

/** 创建下发任务 */
export function createDeployTask(data: DeployCreateRequest) {
  return request<ResponseBase<DeployTask>>({
    url: '/deploy/',
    method: 'post',
    data,
  })
}

/** 审批下发任务 */
export function approveDeployTask(id: string, data: DeployApproveRequest) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}/approve`,
    method: 'post',
    data,
  })
}

/** 执行下发任务 */
export function executeDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}/execute`,
    method: 'post',
  })
}

/** 取消执行中的任务 */
export function cancelDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}/cancel`,
    method: 'post',
  })
}

/** 重试失败的设备 */
export function retryDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}/retry`,
    method: 'post',
  })
}

/** 回滚下发任务 */
export function rollbackDeployTask(id: string) {
  return request<ResponseBase<DeployRollbackResponse>>({
    url: `/deploy/${id}/rollback`,
    method: 'post',
  })
}

export interface DeployBatchResult {
  success_count: number
  failed_ids: string[]
  message?: string
}

/** 获取下发任务回收站列表 */
export function getRecycleBinDeployTasks(params?: DeploySearchParams) {
  return request<ResponseBase<PaginatedResponse<DeployTask>>>({
    url: '/deploy/recycle-bin',
    method: 'get',
    params,
  })
}

/** 删除下发任务（软删除） */
export function deleteDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}`,
    method: 'delete',
  })
}

/** 批量删除下发任务 */
export function batchDeleteDeployTasks(ids: string[]) {
  return request<ResponseBase<DeployBatchResult>>({
    url: '/deploy/batch',
    method: 'delete',
    data: { ids },
  })
}

/** 恢复已删除下发任务 */
export function restoreDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/${id}/restore`,
    method: 'post',
  })
}

/** 批量恢复下发任务 */
export function batchRestoreDeployTasks(ids: string[]) {
  return request<ResponseBase<DeployBatchResult>>({
    url: '/deploy/batch/restore',
    method: 'post',
    data: { ids },
  })
}

/** 彻底删除下发任务 */
export function hardDeleteDeployTask(id: string) {
  return request<ResponseBase<{ message: string }>>({
    url: `/deploy/${id}/hard`,
    method: 'delete',
  })
}

/** 批量彻底删除下发任务 */
export function batchHardDeleteDeployTasks(ids: string[]) {
  return request<ResponseBase<DeployBatchResult>>({
    url: '/deploy/batch/hard',
    method: 'delete',
    data: { ids, hard_delete: true },
  })
}
