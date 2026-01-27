import { useAlertStore } from '@/stores/alert'
import type { AlertType } from '@/stores/alert'

// This helper is designed to work even outside of Setup context
// assuming Pinia instance is active when these are called.
// If called before app mount (rare for this use case), it might fail.

const getStore = () => {
  // We import dynamically or just rely on the fact that Pinia is installed.
  // In Vue 3, using a store outside a component works IF pinia is installed.
  // Since this util is mostly used in API callbacks/Router, app is mounted.
  try {
    return useAlertStore()
  } catch {
    return null
  }
}

export const $alert = {
  success: (content: string, duration = 3000) => {
    getStore()?.add({ type: 'success', content, duration })
  },
  error: (content: string, duration = 3000) => {
    getStore()?.add({ type: 'error', content, duration })
  },
  warning: (content: string, duration = 3000) => {
    getStore()?.add({ type: 'warning', content, duration })
  },
  info: (content: string, duration = 3000) => {
    getStore()?.add({ type: 'info', content, duration })
  },
  add: (type: AlertType, content: string, duration = 3000) => {
    getStore()?.add({ type, content, duration })
  },
}
