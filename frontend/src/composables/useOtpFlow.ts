import { computed, ref } from 'vue'

export interface OtpRequiredDetails {
  dept_id: string
  device_group: string
  failed_devices: string[]
}

type AxiosLikeError = {
  response?: {
    status?: number
    data?: {
      message?: string
      details?: unknown
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
    if (err?.response?.status !== 428) return null
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
