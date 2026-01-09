import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AlertType = 'default' | 'info' | 'success' | 'warning' | 'error'

export interface AlertItem {
  id: string
  type: AlertType
  content: string
  title?: string
  duration?: number // ms, 0 for no auto-dismiss
  closable?: boolean
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref<AlertItem[]>([])

  function add(item: Omit<AlertItem, 'id'> & { id?: string }) {
    // Deduplicate: If an alert with the same content and type exists, ignore.
    const existing = alerts.value.find((a) => a.content === item.content && a.type === item.type)
    if (existing) {
      return existing.id
    }

    const id = item.id || crypto.randomUUID()
    const alertItem: AlertItem = {
      ...item,
      id,
      closable: item.closable ?? true,
    }
    alerts.value.push(alertItem)

    const duration = item.duration ?? 3000
    if (duration > 0) {
      setTimeout(() => {
        remove(id)
      }, duration)
    }
    return id
  }

  function remove(id: string) {
    const index = alerts.value.findIndex((item) => item.id === id)
    if (index !== -1) {
      alerts.value.splice(index, 1)
    }
  }

  function clear() {
    alerts.value = []
  }

  return {
    alerts,
    add,
    remove,
    clear,
  }
})
