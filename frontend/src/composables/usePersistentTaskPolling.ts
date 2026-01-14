import { onMounted, ref } from 'vue'
import { useTaskPolling, type TaskStatusBase, type UseTaskPollingOptions } from './useTaskPolling'

export interface UsePersistentTaskPollingOptions<T extends TaskStatusBase> extends UseTaskPollingOptions<T> {
  storageKey: string
}

export function usePersistentTaskPolling<T extends TaskStatusBase>(
  fetchStatus: (taskId: string) => Promise<{ data: T } | T>,
  options: UsePersistentTaskPollingOptions<T>,
) {
  const { storageKey, ...pollingOptions } = options

  const { taskStatus, isPolling, attempts, start, stop, reset } = useTaskPolling(fetchStatus, pollingOptions)
  const taskId = ref<string | null>(null)

  const setTaskId = (next: string | null) => {
    taskId.value = next
    if (!next) {
      localStorage.removeItem(storageKey)
      return
    }
    localStorage.setItem(storageKey, next)
  }

  const startWithPersistence = (nextTaskId: string, initialStatus?: Partial<T>) => {
    setTaskId(nextTaskId)
    start(nextTaskId, initialStatus)
  }

  const clear = () => {
    setTaskId(null)
    reset()
  }

  onMounted(() => {
    const persisted = localStorage.getItem(storageKey)
    if (persisted) {
      taskId.value = persisted
      start(persisted)
    }
  })

  return {
    taskId,
    taskStatus,
    isPolling,
    attempts,
    start: startWithPersistence,
    stop,
    reset,
    clear,
    setTaskId,
  }
}

