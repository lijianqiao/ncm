/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: useTaskPolling.ts
 * @DateTime: 2026-01-12
 * @Docs: 异步任务状态轮询 Composable
 */

import { ref, onUnmounted, type Ref } from 'vue'
import { $alert } from '@/utils/alert'

/**
 * 任务状态基础接口
 */
export interface TaskStatusBase {
  task_id: string
  status: string
  progress?: number | Record<string, unknown> | null
  result?: unknown
  error?: string | null
}

/**
 * 轮询配置选项
 */
export interface UseTaskPollingOptions<T extends TaskStatusBase> {
  /** 轮询间隔（毫秒），默认 2000 */
  interval?: number
  /** 最大轮询次数，默认 150（5分钟） */
  maxAttempts?: number
  /** 判断任务是否完成的函数 */
  isComplete?: (status: T) => boolean
  /** 任务完成时的回调 */
  onComplete?: (status: T) => void
  /** 任务失败时的回调 */
  onError?: (error: Error) => void
  /** 轮询超时时的回调 */
  onTimeout?: () => void
}

/**
 * 默认判断任务是否完成
 */
function defaultIsComplete(status: TaskStatusBase): boolean {
  const completedStatuses = ['SUCCESS', 'FAILURE', 'success', 'failed', 'REVOKED']
  return completedStatuses.includes(status.status)
}

/**
 * 异步任务状态轮询 Composable
 *
 * @param fetchStatus 获取任务状态的异步函数
 * @param options 轮询配置选项
 * @returns 轮询控制方法和状态
 *
 * @example
 * ```ts
 * const { taskStatus, isPolling, start, stop } = useTaskPolling(
 *   (taskId) => getBackupTaskStatus(taskId),
 *   {
 *     onComplete: (status) => {
 *       if (status.status === 'SUCCESS') tableRef.value?.reload()
 *     }
 *   }
 * )
 *
 * // 开始轮询
 * start(taskId)
 * ```
 */
export function useTaskPolling<T extends TaskStatusBase>(
  fetchStatus: (taskId: string) => Promise<{ data: T } | T>,
  options: UseTaskPollingOptions<T> = {},
) {
  const {
    interval = 2000,
    maxAttempts = 150, // 150 * 2s = 5分钟
    isComplete = defaultIsComplete as (status: T) => boolean,
    onComplete,
    onError,
    onTimeout,
  } = options

  const taskStatus: Ref<T | null> = ref(null)
  const isPolling = ref(false)
  const attempts = ref(0)
  let pollingTimer: ReturnType<typeof setInterval> | null = null

  /**
   * 开始轮询任务状态
   */
  const start = (taskId: string, initialStatus?: Partial<T>) => {
    // 如果已在轮询，先停止
    stop()

    // 设置初始状态
    taskStatus.value = {
      task_id: taskId,
      status: 'PENDING',
      progress: null,
      result: null,
      error: null,
      ...initialStatus,
    } as T

    isPolling.value = true
    attempts.value = 0

    pollingTimer = setInterval(async () => {
      attempts.value++

      // 检查是否超时
      if (attempts.value > maxAttempts) {
        stop()
        $alert.warning('任务轮询超时，请稍后手动检查结果')
        onTimeout?.()
        return
      }

      try {
        const res = await fetchStatus(taskId)
        // 兼容两种返回格式：{ data: T } 或直接返回 T
        const status = 'data' in res ? res.data : res
        taskStatus.value = status

        // 检查任务是否完成
        if (isComplete(status)) {
          stop()
          onComplete?.(status)
        }
      } catch (error) {
        stop()
        onError?.(error instanceof Error ? error : new Error('轮询任务状态失败'))
      }
    }, interval)
  }

  /**
   * 停止轮询
   */
  const stop = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
    isPolling.value = false
  }

  /**
   * 重置状态
   */
  const reset = () => {
    stop()
    taskStatus.value = null
    attempts.value = 0
  }

  // 组件卸载时自动清理
  onUnmounted(() => {
    stop()
  })

  return {
    /** 当前任务状态 */
    taskStatus,
    /** 是否正在轮询 */
    isPolling,
    /** 已轮询次数 */
    attempts,
    /** 开始轮询 */
    start,
    /** 停止轮询 */
    stop,
    /** 重置状态 */
    reset,
  }
}
