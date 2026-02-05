import { computed, ref } from 'vue'
import { verifyOTP } from '@/api/credentials'
import type { OTPCacheRequest } from '@/api/credentials'
import { $alert } from '@/utils/alert'

/** OTP 需求详情（统一数据结构） */
export interface OtpRequiredDetails {
  type?: 'otp_required' | 'otp_timeout' | string
  message?: string
  otp_credential_id?: string | null
  otp_credential_username?: string | null
  otp_credential_device_group?: string | null
  otp_failed_device_ids?: string[]
  otp_wait_status?: 'waiting' | 'timeout' | 'ready' | string | null
  otp_wait_timeout?: number | null
  otp_cache_ttl?: number | null
  pending_device_ids?: string[]
  task_id?: string
  next_action?: string | null
}

type AxiosLikeError = {
  response?: {
    status?: number
    data?: {
      code?: number
      message?: string
      details?: unknown
      data?: {
        otp_notice?: unknown
      }
    }
  }
}

type InfoItem = { label: string; value: string }

export function useOtpFlow(options?: { length?: number }) {
  const length = options?.length ?? 6
  const maxListItems = 3

  const show = ref(false)
  const loading = ref(false)
  const details = ref<OtpRequiredDetails | null>(null)
  const pendingAction = ref<((otpCode: string) => Promise<void>) | null>(null)
  const errorMessage = ref('')
  const queue = ref<Array<{ details: OtpRequiredDetails; action: (otpCode: string) => Promise<void> }>>([])
  const queueCount = computed(() => queue.value.length)

  const buildKey = (d: OtpRequiredDetails) => {
    return `${d.otp_credential_id || ''}|${d.otp_credential_device_group || ''}|${d.task_id || ''}`
  }

  const applyNext = () => {
    if (queue.value.length === 0) return
    const next = queue.value.shift()
    if (!next) return
    details.value = next.details
    pendingAction.value = next.action
    show.value = true
    errorMessage.value = ''
  }

  const formatListValue = (value: string | string[]): string => {
    if (Array.isArray(value)) {
      if (value.length > maxListItems) {
        return `${value.slice(0, maxListItems).join(', ')} ...`
      }
      return value.join(', ')
    }
    const parts = value.split(/[,，、]\s*/).filter(Boolean)
    if (parts.length > 1) {
      if (parts.length > maxListItems) {
        return `${parts.slice(0, maxListItems).join(', ')} ...`
      }
      return parts.join(', ')
    }
    return value
  }

  const infoItems = computed<InfoItem[]>(() => {
    const d = details.value
    if (!d) return []
    const items: InfoItem[] = []

    if (d.otp_credential_username) {
      items.push({ label: '凭据账号', value: formatListValue(d.otp_credential_username) })
    }
    if (d.otp_credential_id && !d.otp_credential_username) {
      items.push({ label: '凭据ID', value: formatListValue(d.otp_credential_id) })
    }
    if (d.otp_credential_device_group) {
      items.push({ label: '设备组', value: formatListValue(d.otp_credential_device_group) })
    }
    if (d.otp_failed_device_ids && d.otp_failed_device_ids.length > 0) {
      const preview = d.otp_failed_device_ids.slice(0, maxListItems)
      const suffix = d.otp_failed_device_ids.length > maxListItems ? ' ...' : ''
      items.push({ label: '失败设备', value: `${preview.join(', ')}${suffix}` })
    }
    return items
  })

  const idleTimeoutMs = computed(() => {
    const d = details.value
    const waitSeconds = d?.otp_wait_timeout
    if (typeof waitSeconds === 'number' && waitSeconds > 0) {
      return Math.floor(waitSeconds * 1000)
    }
    return 60_000
  })

  const open = (nextDetails: OtpRequiredDetails, action: (otpCode: string) => Promise<void>) => {
    const nextKey = buildKey(nextDetails)
    if (details.value && buildKey(details.value) === nextKey) return
    if (queue.value.some(item => buildKey(item.details) === nextKey)) return
    queue.value.push({ details: nextDetails, action })
    if (!show.value) {
      applyNext()
    }
  }

  const close = () => {
    if (loading.value) return
    show.value = false
    details.value = null
    pendingAction.value = null
    errorMessage.value = ''
    applyNext()
  }

  const handleTimeout = () => {
    // 超时关闭时，清理状态并提示用户
    show.value = false
    details.value = null
    pendingAction.value = null
    errorMessage.value = ''
    $alert.warning('OTP 输入超时，请重新操作')
    applyNext()
  }

  const extractOtpRequiredDetails = (error: unknown): OtpRequiredDetails | null => {
    const err = error as AxiosLikeError
    const status = err?.response?.status
    const code = err?.response?.data?.code

    // 支持 HTTP 428 或 业务码 428
    if (status !== 428 && code !== 428) return null

    // 1. 优先从 details 获取
    const details = err?.response?.data?.details as {
      otp_required?: boolean
      otp_credential_id?: string
      otp_credential_username?: string
      otp_credential_device_group?: string
      otp_failed_device_ids?: string[]
      otp_wait_status?: string
      otp_wait_timeout?: number
      otp_cache_ttl?: number
      pending_device_ids?: string[]
      task_id?: string
      next_action?: string
    } | undefined

    if (details?.otp_credential_id) {
      return {
        otp_credential_id: details.otp_credential_id,
        otp_credential_username: details.otp_credential_username,
        otp_credential_device_group: details.otp_credential_device_group,
        otp_failed_device_ids: details.otp_failed_device_ids || [],
        otp_wait_status: details.otp_wait_status,
        otp_wait_timeout: details.otp_wait_timeout,
        otp_cache_ttl: details.otp_cache_ttl,
        pending_device_ids: details.pending_device_ids,
        task_id: details.task_id,
        next_action: details.next_action,
        message: err?.response?.data?.message || '需要 OTP 验证',
      }
    }

    // 2. 尝试从 data 直接获取（428 响应体）
    const data = err?.response?.data?.data as {
      otp_required?: boolean
      otp_credential_id?: string
      otp_credential_username?: string
      otp_credential_device_group?: string
      otp_failed_device_ids?: string[]
      otp_wait_status?: string
      otp_wait_timeout?: number
      otp_cache_ttl?: number
      pending_device_ids?: string[]
      task_id?: string
      next_action?: string
      otp_credentials?: Array<{
        otp_credential_id?: string
        otp_credential_username?: string
        otp_credential_device_group?: string
        otp_failed_device_ids?: string[]
        pending_device_ids?: string[]
        otp_wait_status?: string
      }>
    } | undefined

    // 2.1 检查 otp_credentials
    if (data?.otp_credentials && data.otp_credentials.length > 0) {
      const first = data.otp_credentials[0]
      if (first) {
        return {
          otp_credential_id: first.otp_credential_id,
          otp_credential_username: first.otp_credential_username,
          otp_credential_device_group: first.otp_credential_device_group,
          otp_failed_device_ids: first.otp_failed_device_ids || [],
          otp_wait_status: first.otp_wait_status,
          otp_wait_timeout: data.otp_wait_timeout,
          otp_cache_ttl: data.otp_cache_ttl,
          pending_device_ids: first.pending_device_ids || data.pending_device_ids,
          task_id: data.task_id,
          next_action: data.next_action,
          message: err?.response?.data?.message || '需要 OTP 验证',
        }
      }
    }

    // 2.2 从 data 直接获取单个凭据信息
    if (data?.otp_credential_id) {
      return {
        otp_credential_id: data.otp_credential_id,
        otp_credential_username: data.otp_credential_username,
        otp_credential_device_group: data.otp_credential_device_group,
        otp_failed_device_ids: data.otp_failed_device_ids || [],
        otp_wait_status: data.otp_wait_status,
        otp_wait_timeout: data.otp_wait_timeout,
        otp_cache_ttl: data.otp_cache_ttl,
        pending_device_ids: data.pending_device_ids,
        task_id: data.task_id,
        next_action: data.next_action,
        message: err?.response?.data?.message || '需要 OTP 验证',
      }
    }

    // 3. 尝试从 data.otp_notice 获取（任务状态中的 OTP 提示）
    const otpNotice = err?.response?.data?.data?.otp_notice as OtpRequiredDetails | undefined
    if (otpNotice?.otp_credential_id) {
      return {
        type: otpNotice.type,
        message: otpNotice.message,
        otp_credential_id: otpNotice.otp_credential_id,
        otp_credential_username: otpNotice.otp_credential_username,
        otp_credential_device_group: otpNotice.otp_credential_device_group,
        otp_failed_device_ids: otpNotice.otp_failed_device_ids || [],
        otp_wait_status: otpNotice.otp_wait_status,
        otp_wait_timeout: otpNotice.otp_wait_timeout,
        otp_cache_ttl: otpNotice.otp_cache_ttl,
        pending_device_ids: otpNotice.pending_device_ids,
        task_id: otpNotice.task_id,
        next_action: otpNotice.next_action,
      }
    }

    return null
  }

  const confirm = async (otpCode: string) => {
    const action = pendingAction.value
    if (!action) return
    if (otpCode.trim().length !== length) {
      errorMessage.value = `请输入 ${length} 位验证码`
      return
    }

    loading.value = true
    errorMessage.value = ''

    const d = details.value
    if (!d) {
      loading.value = false
      return
    }

    try {
      if (!d.otp_credential_id) {
        errorMessage.value = '缺少 OTP 凭据信息，请重新操作'
        return
      }
      const verifyPayload = {
        credential_id: d.otp_credential_id,
        otp_code: otpCode.trim(),
      }

      const verifyRes = await verifyOTP(verifyPayload)

      if (verifyRes.data?.verified) {
        $alert.success(verifyRes.data.message || 'OTP 验证成功')
        // 2. 验证成功后关闭弹窗
        show.value = false
        details.value = null
        // 这里不要清空 pendingAction，因为下面还要用
        // pendingAction.value = null
        errorMessage.value = ''

        // 关键修复：在执行后续耗时操作前，必须结束 loading 状态
        // 否则如果后续操作触发新的 428 弹窗，loading=true 会导致新弹窗不可输入
        loading.value = false

        // 3. 执行后续操作（即重试原请求）
        await action(otpCode.trim())
        // 执行完后再清空
        pendingAction.value = null
        applyNext()
      }
    } catch (error: unknown) {
      const err = error as AxiosLikeError
      const status = err?.response?.status
      const msg = err?.response?.data?.message

      if (status === 428) {
        // 验证失败，保持弹窗，提示错误
        errorMessage.value = '验证码错误或已过期，请重新输入'
        // 不关闭弹窗，让用户重试
      } else {
        // 其他错误 (400 等)
        errorMessage.value = msg || '验证失败，请重试'
      }
    } finally {
      // 只有当 loading 为 true 时才重置（避免覆盖我们在 try 块中手动设置的 false）
      // 其实这里再次设置 false 也没问题，只要确保 try 块中 await action 之前已经设为 false
      if (loading.value) loading.value = false
    }
  }

  const tryHandleOtpRequired = (
    error: unknown,
    action: (otpCode: string) => Promise<void>,
  ): boolean => {
    const d = extractOtpRequiredDetails(error)
    if (!d) {
      return false
    }
    open(d, action)
    return true
  }

  return {
    length,
    show,
    loading,
    details,
    infoItems,
    errorMessage,
    idleTimeoutMs,
    queueCount,
    open,
    close,
    confirm,
    handleTimeout,
    tryHandleOtpRequired,
  }
}

// 创建一个全局的 otpFlow 实例，用于处理全局的 428 响应（如 request.ts 拦截器）
export const globalOtpFlow = useOtpFlow()
