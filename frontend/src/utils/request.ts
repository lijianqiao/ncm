/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: request.ts
 * @DateTime: 2026-01-08
 * @Docs: Axios 请求封装，支持 HttpOnly Cookie + CSRF 认证方案
 */

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { $alert } from '@/utils/alert'
import { getCsrfToken } from '@/utils/cookie'
import router from '@/router'
import type { ResponseBase } from '@/types/api'

// 内存中存储的 Access Token（不再使用 localStorage）
let accessToken: string | null = null

/**
 * 获取当前 Access Token
 */
export function getAccessToken(): string | null {
  return accessToken
}

/**
 * 设置 Access Token
 */
export function setAccessToken(token: string | null): void {
  accessToken = token
}

/**
 * 清除 Access Token
 */
export function clearAccessToken(): void {
  accessToken = null
}

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  // 跨域情况下必须开启，确保 Cookie 能够被发送
  withCredentials: true,
})

interface RetryAxiosRequestConfig extends AxiosRequestConfig {
  _retry?: boolean
}

// 请求取消管理器
const pendingRequests = new Map<string, AbortController>()

/**
 * 生成请求唯一标识
 */
function generateRequestKey(config: AxiosRequestConfig): string {
  const { method, url, params, data } = config
  return `${method}:${url}:${JSON.stringify(params || {})}:${JSON.stringify(data || {})}`
}

/**
 * 添加待处理请求
 */
function addPendingRequest(config: AxiosRequestConfig): void {
  const requestKey = generateRequestKey(config)
  if (pendingRequests.has(requestKey)) {
    // 取消之前的相同请求
    const controller = pendingRequests.get(requestKey)
    controller?.abort()
  }
  const controller = new AbortController()
  config.signal = controller.signal
  pendingRequests.set(requestKey, controller)
}

/**
 * 移除已完成的请求
 */
function removePendingRequest(config: AxiosRequestConfig): void {
  const requestKey = generateRequestKey(config)
  pendingRequests.delete(requestKey)
}

/**
 * 取消所有待处理请求
 */
export function cancelAllRequests(): void {
  pendingRequests.forEach((controller) => {
    controller.abort()
  })
  pendingRequests.clear()
}

/**
 * 取消指定请求
 */
export function cancelRequest(method: string, url: string): void {
  const pattern = `${method}:${url}`
  pendingRequests.forEach((controller, key) => {
    if (key.startsWith(pattern)) {
      controller.abort()
      pendingRequests.delete(key)
    }
  })
}

// Token 刷新状态管理
let isRefreshing = false
let refreshSubscribers: Array<{
  resolve: (token: string) => void
  reject: (error: Error) => void
}> = []

/**
 * 订阅 Token 刷新完成事件
 */
function subscribeTokenRefresh(
  resolve: (token: string) => void,
  reject: (error: Error) => void,
): void {
  refreshSubscribers.push({ resolve, reject })
}

/**
 * 通知所有订阅者 Token 刷新完成
 */
function onTokenRefreshed(newToken: string): void {
  refreshSubscribers.forEach(({ resolve }) => resolve(newToken))
  refreshSubscribers = []
}

/**
 * 通知所有订阅者 Token 刷新失败
 */
function onTokenRefreshFailed(error: Error): void {
  refreshSubscribers.forEach(({ reject }) => reject(error))
  refreshSubscribers = []
}

/**
 * 执行 Token 刷新
 * 使用 HttpOnly Cookie 中的 Refresh Token + CSRF Token
 */
async function doRefreshToken(): Promise<string> {
  const csrfToken = getCsrfToken()

  const response = await axios.post(
    `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/refresh`,
    {},
    {
      withCredentials: true,
      headers: {
        'X-CSRF-Token': csrfToken || '',
      },
    },
  )

  // 后端返回新的 access_token
  const newAccessToken = response.data?.data?.access_token || response.data?.access_token
  if (!newAccessToken) {
    throw new Error('刷新 Token 返回数据异常')
  }

  return newAccessToken
}

/**
 * 处理登录过期/刷新失败
 */
function handleAuthFailure(): void {
  clearAccessToken()

  // 避免重复跳转
  if (router.currentRoute.value.name !== 'Login') {
    $alert.error('登录已过期，请重新登录')
    router.push({ name: 'Login', query: { redirect: router.currentRoute.value.fullPath } })
  }
}

// 请求拦截器（支持取消）
service.interceptors.request.use(
  (config) => {
    // 添加请求到待处理列表（支持取消）
    addPendingRequest(config)

    // 从内存读取 Access Token
    if (accessToken) {
      config.headers['Authorization'] = `Bearer ${accessToken}`
    }

    // 为状态修改请求添加 CSRF Token
    const method = config.method?.toLowerCase()
    if (method && ['post', 'put', 'delete', 'patch'].includes(method)) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

const responseSuccessInterceptor = (response: AxiosResponse): unknown => {
  // 移除已完成的请求
  removePendingRequest(response.config)

  const url = response.config?.url || ''
  const responseType = response.config?.responseType
  if (responseType === 'blob' || responseType === 'arraybuffer') {
    return response
  }
  if (url.includes('/auth/login')) {
    return response.data
  }

  const res = response.data as ResponseBase<unknown>

  const is2xx = response.status >= 200 && response.status < 300
  if (!is2xx) {
    $alert.error(res.message || '请求错误')
    throw new Error(res.message || '请求错误')
  }

  if (res.code !== 200) {
    $alert.error(res.message || '请求错误')
    throw new Error(res.message || '请求错误')
  }

  return res
}

const responseErrorInterceptor = async (error: unknown) => {
  if (!axios.isAxiosError(error)) {
    $alert.error('请求失败')
    return Promise.reject(error)
  }

  // 移除已完成的请求
  if (error.config) {
    removePendingRequest(error.config)
  }

  const isCanceled =
    axios.isCancel(error) ||
    error?.code === 'ERR_CANCELED' ||
    error?.name === 'CanceledError' ||
    error?.name === 'AbortError'
  if (isCanceled) return Promise.reject(error)

  const originalRequest = error.config as RetryAxiosRequestConfig | undefined

  // 网络错误等无响应情况
  if (!error.response) {
    $alert.error(error.message || '网络请求失败')
    return Promise.reject(error)
  }

  const { status } = error.response
  const responseData = error.response.data as { message?: string } | undefined
  const msg = responseData?.message || error.message || '请求失败'

  // 处理 401 未授权错误
  if (status === 401 && originalRequest && !originalRequest._retry) {
    // 排除登录和刷新接口本身
    if (
      originalRequest.url?.includes('/auth/login') ||
      originalRequest.url?.includes('/auth/refresh')
    ) {
      // 刷新接口本身 401，说明 Refresh Token 已失效
      if (originalRequest.url?.includes('/auth/refresh')) {
        handleAuthFailure()
      }
      return Promise.reject(error)
    }

    // 标记已重试，防止无限循环
    originalRequest._retry = true

    // 并发控制：如果正在刷新，则排队等待
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        subscribeTokenRefresh(
          (newToken: string) => {
            originalRequest.headers = originalRequest.headers || {}
            ;(originalRequest.headers as Record<string, string>)['Authorization'] =
              `Bearer ${newToken}`
            resolve(service(originalRequest))
          },
          (error: Error) => {
            reject(error)
          },
        )
      })
    }

    // 开始刷新流程
    isRefreshing = true

    try {
      const newToken = await doRefreshToken()

      // 更新内存中的 Token
      setAccessToken(newToken)

      // 更新默认请求头
      service.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
      originalRequest.headers = originalRequest.headers || {}
      ;(originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`

      // 通知排队的请求
      onTokenRefreshed(newToken)

      // 重放原始请求
      return service(originalRequest)
    } catch (refreshErr) {
      onTokenRefreshFailed(refreshErr instanceof Error ? refreshErr : new Error('Token 刷新失败'))
      handleAuthFailure()
      return Promise.reject(refreshErr)
    } finally {
      isRefreshing = false
    }
  }

  // 处理 403 权限不足
  if (status === 403) {
    $alert.warning('权限不足')
  } else if (status >= 400) {
    // 其他错误统一提示
    $alert.error(msg)
  }

  return Promise.reject(error)
}

// 响应拦截器
service.interceptors.response.use(
  responseSuccessInterceptor as unknown as (
    response: AxiosResponse,
  ) => AxiosResponse | Promise<AxiosResponse>,
  responseErrorInterceptor,
)

// 请求方法封装
export const request = <T = unknown>(config: AxiosRequestConfig): Promise<T> => {
  return service.request(config) as unknown as Promise<T>
}

export default service
