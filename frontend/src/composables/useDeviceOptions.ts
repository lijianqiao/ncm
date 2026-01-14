import { computed, ref } from 'vue'
import { getDevices, type Device, type DeviceSearchParams } from '@/api/devices'

type DeviceOption = { label: string; value: string }

type CacheEntry = {
  expiresAt: number
  options: DeviceOption[]
  devicesById: Record<string, Device>
}

const deviceOptionsCache = new Map<string, CacheEntry>()

export interface UseDeviceOptionsOptions {
  status?: DeviceSearchParams['status']
  deptId?: DeviceSearchParams['dept_id']
  pageSize?: number
  cacheKey?: string
  cacheTtlMs?: number
  immediate?: boolean
  label?: (device: Device) => string
}

export function useDeviceOptions(options: UseDeviceOptionsOptions = {}) {
  const {
    status = 'active',
    deptId,
    pageSize = 100,
    cacheKey,
    cacheTtlMs = 30_000,
    immediate = false,
    label = (d) => `${d.name} (${d.ip_address})`,
  } = options

  const loading = ref(false)
  const deviceOptions = ref<DeviceOption[]>([])
  const devicesById = ref<Record<string, Device>>({})

  const resolvedCacheKey = computed(() => {
    if (cacheKey) return cacheKey
    return JSON.stringify({ status, deptId, pageSize })
  })

  const readCache = () => {
    const entry = deviceOptionsCache.get(resolvedCacheKey.value)
    if (!entry) return null
    if (Date.now() > entry.expiresAt) {
      deviceOptionsCache.delete(resolvedCacheKey.value)
      return null
    }
    return entry
  }

  const writeCache = (next: CacheEntry) => {
    deviceOptionsCache.set(resolvedCacheKey.value, next)
  }

  const load = async (force = false) => {
    const cached = !force ? readCache() : null
    if (cached) {
      deviceOptions.value = cached.options
      devicesById.value = cached.devicesById
      return { options: cached.options, devicesById: cached.devicesById }
    }

    loading.value = true
    try {
      const params: DeviceSearchParams = { status, page_size: pageSize }
      if (deptId) params.dept_id = deptId

      const res = await getDevices(params)
      const items = res.data.items || []

      const nextMap: Record<string, Device> = {}
      for (const d of items) nextMap[d.id] = d

      const nextOptions = items.map((d) => ({ label: label(d), value: d.id }))
      deviceOptions.value = nextOptions
      devicesById.value = nextMap

      writeCache({
        expiresAt: Date.now() + cacheTtlMs,
        options: nextOptions,
        devicesById: nextMap,
      })

      return { options: nextOptions, devicesById: nextMap }
    } finally {
      loading.value = false
    }
  }

  if (immediate) {
    void load()
  }

  const getDevice = (deviceId: string) => {
    return devicesById.value[deviceId] || null
  }

  return {
    deviceOptions,
    devicesById,
    loading,
    load,
    refresh: () => load(true),
    getDevice,
  }
}

