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

  const show = ref(false)
  const loading = ref(false)
  const details = ref<OtpRequiredDetails | null>(null)
  const pendingAction = ref<((otpCode: string) => Promise<void>) | null>(null)
  const errorMessage = ref('')

  const infoItems = computed<InfoItem[]>(() => {
    const d = details.value
    if (!d) return []
    const items: InfoItem[] = [
      { label: '部门ID', value: d.dept_id },
      { label: '设备组', value: d.device_group },
    ]
    if (d.failed_devices && d.failed_devices.length > 0) {
      items.push({ label: '失败设备', value: d.failed_devices.join(', ') })
    }
    return items
  })

  const open = (nextDetails: OtpRequiredDetails, action: (otpCode: string) => Promise<void>) => {
    details.value = nextDetails
    pendingAction.value = action
    show.value = true
    errorMessage.value = ''
  }

  const close = () => {
    if (loading.value) return
    show.value = false
    details.value = null
    pendingAction.value = null
    errorMessage.value = ''
  }

  const extractOtpRequiredDetails = (error: unknown): OtpRequiredDetails | null => {
    const err = error as AxiosLikeError
    const status = err?.response?.status
    const code = err?.response?.data?.code

    // 支持 HTTP 428 或 业务码 428
    if (status !== 428 && code !== 428) return null

    // 1. 尝试从 data.otp_required_groups 获取 (新结构 - 列表)
    const data = err?.response?.data?.data as {
      otp_required_groups?: Array<{ dept_id: string; device_group: string }>
      dept_id?: string
      device_group?: string
      failed_devices?: string[]
      otp_required?: boolean
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

    // 2. 尝试从 data 直接获取 (新结构 - 单个)
    if (data && data.dept_id && data.device_group) {
      return {
        dept_id: data.dept_id,
        device_group: data.device_group,
        failed_devices: data.failed_devices || [],
        message: err?.response?.data?.message || '需要 OTP 验证',
      }
    }

    // 3. 优先尝试从 data.otp_notice 获取 (旧结构)
    const otpNotice = err?.response?.data?.data?.otp_notice as OtpRequiredDetails | undefined
    if (otpNotice && otpNotice.dept_id && otpNotice.device_group) {
      return {
        type: otpNotice.type,
        message: otpNotice.message,
        dept_id: otpNotice.dept_id,
        device_group: otpNotice.device_group,
        failed_devices: otpNotice.failed_devices || [],
        pending_device_ids: otpNotice.pending_device_ids,
      }
    }

    // 兼容旧结构 details
    const d = err?.response?.data?.details as OtpRequiredDetails | undefined
    if (!d || !d.dept_id || !d.device_group) return null
    return {
      dept_id: d.dept_id,
      device_group: d.device_group,
      failed_devices: d.failed_devices || [],
    }
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
        pendingAction.value = null
        errorMessage.value = ''
        // 3. 执行后续操作（即重试原请求）
        await action(otpCode.trim())
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
      loading.value = false
    }
  }

  const tryHandleOtpRequired = (
    error: unknown,
    action: (otpCode: string) => Promise<void>,
  ): boolean => {
    const d = extractOtpRequiredDetails(error)
    if (!d) return false

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
    open,
    close,
    confirm,
    tryHandleOtpRequired,
  }
}

// 创建一个全局的 otpFlow 实例，用于处理全局的 428 响应（如 request.ts 拦截器）
export const globalOtpFlow = useOtpFlow()
