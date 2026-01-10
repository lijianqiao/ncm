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
  | 'executing'
  | 'success'
  | 'failed'
  | 'rollback'

// ==================== 接口定义 ====================

/** 下发计划 */
export interface DeployPlan {
  scheduled_at?: string
  execute_mode?: 'serial' | 'parallel'
  batch_size?: number
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
  description: string | null
  template_id: string
  template_name: string | null
  template_params: Record<string, unknown> | null
  rendered_content: string | null
  device_ids: string[]
  status: DeployTaskStatus
  change_description: string | null
  impact_scope: string | null
  rollback_plan: string | null
  deploy_plan: DeployPlan | null
  approvals: ApprovalRecord[]
  device_results: DeviceDeployResult[]
  celery_task_id: string | null
  created_by: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string | null
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
    url: '/deploy/deploy/',
    method: 'get',
    params,
  })
}

/** 获取下发任务详情 */
export function getDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/deploy/${id}`,
    method: 'get',
  })
}

/** 创建下发任务 */
export function createDeployTask(data: DeployCreateRequest) {
  return request<ResponseBase<DeployTask>>({
    url: '/deploy/deploy/',
    method: 'post',
    data,
  })
}

/** 审批下发任务 */
export function approveDeployTask(id: string, data: DeployApproveRequest) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/deploy/${id}/approve`,
    method: 'post',
    data,
  })
}

/** 执行下发任务 */
export function executeDeployTask(id: string) {
  return request<ResponseBase<DeployTask>>({
    url: `/deploy/deploy/${id}/execute`,
    method: 'post',
  })
}

/** 回滚下发任务 */
export function rollbackDeployTask(id: string) {
  return request<ResponseBase<DeployRollbackResponse>>({
    url: `/deploy/deploy/${id}/rollback`,
    method: 'post',
  })
}
