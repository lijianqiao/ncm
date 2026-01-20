import { computed, ref } from 'vue'

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
  }

  const close = () => {
    if (loading.value) return
    show.value = false
    details.value = null
    pendingAction.value = null
  }

  const extractOtpRequiredDetails = (error: unknown): OtpRequiredDetails | null => {
    const err = error as AxiosLikeError
    const status = err?.response?.status
    const code = err?.response?.data?.code

    // 支持 HTTP 428 或 业务码 428
    if (status !== 428 && code !== 428) return null

    // 优先尝试从 data.otp_notice 获取
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
    if (otpCode.trim().length !== length) return

    show.value = false
    loading.value = true
    try {
      await action(otpCode.trim())
      details.value = null
      pendingAction.value = null
    } catch (error: unknown) {
      const nextDetails = extractOtpRequiredDetails(error)
      if (nextDetails) {
        details.value = nextDetails
        pendingAction.value = action
        show.value = true
      } else {
        details.value = null
        pendingAction.value = null
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
    open,
    close,
    confirm,
    tryHandleOtpRequired,
  }
}
