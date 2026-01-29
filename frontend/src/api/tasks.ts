/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: tasks.ts
 * @DateTime: 2026-01-29
 * @Docs: 任务相关 API
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

export interface ResumeTaskResponse {
  task_id: string
  resume_task_id?: string
  celery_task_id?: string
}

export function resumeTaskGroup(taskId: string, params: { dept_id: string; group: string }) {
  return request<ResponseBase<ResumeTaskResponse>>({
    url: `/tasks/${taskId}/resume`,
    method: 'post',
    params,
    skipOtpHandling: true,
  })
}
