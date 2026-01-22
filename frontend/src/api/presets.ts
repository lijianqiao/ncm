/**
 * 预设模板 API
 */
import type { ResponseBase } from '@/types/api'
import { request } from '@/utils/request'

/** 预设模板简要信息 */
export interface PresetInfo {
  id: string
  name: string
  description: string
  category: 'show' | 'config'
  supported_vendors: string[]
}

/** 预设模板详情 */
export interface PresetDetail extends PresetInfo {
  parameters_schema: Record<string, unknown>
}

/** 执行预设请求 */
export interface PresetExecuteRequest {
  device_id: string
  params: Record<string, unknown>
}

/** 执行预设结果 */
export interface PresetExecuteResult {
  success: boolean
  raw_output: string
  parsed_output: unknown
  parse_error: string | null
  error_message: string | null

  otp_required?: boolean
  otp_required_groups?: Array<{ dept_id: string; device_group: string }>
  expires_in?: number | null
  next_action?: string | null
}

/** 获取预设列表 */
export function getPresets() {
  return request<ResponseBase<PresetInfo[]>>({
    url: '/presets/',
    method: 'get',
  })
}

/** 获取预设详情 */
export function getPreset(presetId: string) {
  return request<ResponseBase<PresetDetail>>({
    url: `/presets/${presetId}`,
    method: 'get',
  })
}

/** 执行预设操作 */
export function executePreset(presetId: string, data: PresetExecuteRequest) {
  return request<ResponseBase<PresetExecuteResult>>({
    url: `/presets/${presetId}/execute`,
    method: 'post',
    data,
    timeout: 60000, // 设置超时时间为 60 秒
  })
}
