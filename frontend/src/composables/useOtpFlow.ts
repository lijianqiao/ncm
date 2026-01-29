import { computed, ref } from 'vue'
import { verifyOTP } from '@/api/credentials'
import type { DeviceGroup } from '@/api/devices'
import { $alert } from '@/utils/alert'

export interface OtpRequiredDetails {
  type?: string
  message?: string
  dept_id: string
  device_group: string
  failed_devices: string[]
  pending_device_ids?: string[]
  task_id?: string
  otp_wait_status?: string
  otp_wait_timeout?: number
  otp_cache_ttl?: number
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

  const buildKey = (d: OtpRequiredDetails) => `${d.dept_id}|${d.device_group}|${d.task_id || ''}`

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
    const items: InfoItem[] = [
      { label: '部门ID', value: formatListValue(d.dept_id) },
      { label: '设备组', value: formatListValue(d.device_group) },
    ]
    if (d.failed_devices && d.failed_devices.length > 0) {
      const preview = d.failed_devices.slice(0, maxListItems)
      const suffix = d.failed_devices.length > maxListItems ? ' ...' : ''
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

    // 1. 优先从 details 获取（最新结构）
    const details = err?.response?.data?.details as {
      otp_required?: boolean
      dept_id?: string
      device_group?: string
      failed_devices?: string[]
      task_id?: string
      otp_wait_status?: string
      otp_wait_timeout?: number
      otp_cache_ttl?: number
    } | undefined

    if (details && details.dept_id && details.device_group) {
      return {
        dept_id: details.dept_id,
        device_group: details.device_group,
        failed_devices: details.failed_devices || [],
        message: err?.response?.data?.message || '需要 OTP 验证',
        task_id: details.task_id,
        otp_wait_status: details.otp_wait_status,
        otp_wait_timeout: details.otp_wait_timeout,
        otp_cache_ttl: details.otp_cache_ttl,
      }
    }

    // 2. 尝试从 data.otp_required_groups 获取 (列表结构)
    const data = err?.response?.data?.data as {
      otp_required_groups?: Array<{ dept_id: string; device_group: string }>
      dept_id?: string
      device_group?: string
      failed_devices?: string[]
      otp_required?: boolean
      task_id?: string
      otp_wait_status?: string
    } | undefined

    if (data?.otp_required_groups && data.otp_required_groups.length > 0) {
      const first = data.otp_required_groups[0]
      if (first) {
        return {
          dept_id: first.dept_id,
          device_group: first.device_group,
          failed_devices: [],
          message: err?.response?.data?.message || '回滚需要输入 OTP',
        }
      }
    }

    // 3. 尝试从 data 直接获取
    if (data && data.dept_id && data.device_group) {
      return {
        dept_id: data.dept_id,
        device_group: data.device_group,
        failed_devices: data.failed_devices || [],
        message: err?.response?.data?.message || '需要 OTP 验证',
        task_id: (data as { task_id?: string }).task_id,
        otp_wait_status: (data as { otp_wait_status?: string }).otp_wait_status,
        otp_wait_timeout: (data as { otp_wait_timeout?: number }).otp_wait_timeout,
        otp_cache_ttl: (data as { otp_cache_ttl?: number }).otp_cache_ttl,
      }
    }

    // 4. 优先尝试从 data.otp_notice 获取 (旧结构)
    const otpNotice = err?.response?.data?.data?.otp_notice as OtpRequiredDetails | undefined
    if (otpNotice && otpNotice.dept_id && otpNotice.device_group) {
      return {
        type: otpNotice.type,
        message: otpNotice.message,
        dept_id: otpNotice.dept_id,
        device_group: otpNotice.device_group,
        failed_devices: otpNotice.failed_devices || [],
        pending_device_ids: otpNotice.pending_device_ids,
        task_id: otpNotice.task_id,
        otp_wait_status: otpNotice.otp_wait_status,
        otp_wait_timeout: otpNotice.otp_wait_timeout,
        otp_cache_ttl: otpNotice.otp_cache_ttl,
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
      // 1. 先验证 OTP
      // 注意：DeviceGroup 类型在 api/devices 中定义，这里简单的强制转换，或者在 api 调用时兼容 string
      // 实际上后端需要的是 string 类型的枚举值
      const verifyRes = await verifyOTP({
        dept_id: d.dept_id,
        device_group: d.device_group as DeviceGroup,
        otp_code: otpCode.trim(),
      })

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
    let d = extractOtpRequiredDetails(error)
    if (!d) {
      const err = error as AxiosLikeError
      const status = err?.response?.status
      const code = err?.response?.data?.code
      if (status !== 428 && code !== 428) return false
      d = {
        dept_id: '未知',
        device_group: '未知',
        failed_devices: [],
        message: err?.response?.data?.message || '需要 OTP 验证',
      }
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
