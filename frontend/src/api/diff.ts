/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: diff.ts
 * @DateTime: 2026-01-10
 * @Docs: 配置差异对比 API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

// ==================== 接口定义 ====================

/** 差异响应接口 */
export interface DiffResponse {
  device_id: string
  device_name: string | null
  old_backup_id: string | null
  new_backup_id: string | null
  old_hash: string | null
  new_hash: string | null
  diff_content: string | null
  has_changes: boolean
  created_at: string | null
}

// ==================== API 函数 ====================

/** 获取设备最新配置差异 */
export function getDeviceLatestDiff(deviceId: string) {
  return request<ResponseBase<DiffResponse>>({
    url: `/diff/device/${deviceId}/latest`,
    method: 'get',
  })
}
