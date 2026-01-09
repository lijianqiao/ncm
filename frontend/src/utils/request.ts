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

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 从内存读取 Access Token
    if (accessToken) {
      config.headers['Authorization'] = `Bearer ${accessToken}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// Token 刷新状态管理
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

/**
 * 订阅 Token 刷新完成事件
 */
function subscribeTokenRefresh(callback: (token: string) => void): void {
  refreshSubscribers.push(callback)
}

/**
 * 通知所有订阅者 Token 刷新完成
 */
function onTokenRefreshed(newToken: string): void {
  refreshSubscribers.forEach((callback) => callback(newToken))
  refreshSubscribers = []
}

/**
 * 通知所有订阅者 Token 刷新失败
 */
function onTokenRefreshFailed(): void {
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
  const newAccessToken = response.data?.access_token
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

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse<ResponseBase>) => {
    const res = response.data
    // 成功响应
    if (response.status === 200) {
      return res as unknown as AxiosResponse
    }
    $alert.error(res.message || '请求错误')
    return Promise.reject(new Error(res.message || '请求错误'))
  },
  async (error) => {
    const originalRequest = error.config

    // 网络错误等无响应情况
    if (!error.response) {
      $alert.error(error.message || '网络请求失败')
      return Promise.reject(error)
    }

    const { status } = error.response
    const msg = error.response?.data?.message || error.message || '请求失败'

    // 处理 401 未授权错误
    if (status === 401 && !originalRequest._retry) {
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
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            originalRequest.headers['Authorization'] = `Bearer ${newToken}`
            resolve(service(originalRequest))
          })
          // 刷新失败时由 handleAuthFailure 统一处理跳转登录页
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
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`

        // 通知排队的请求
        onTokenRefreshed(newToken)

        // 重放原始请求
        return service(originalRequest)
      } catch (refreshErr) {
        console.error('Token 刷新失败:', refreshErr)
        onTokenRefreshFailed()
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
  },
)

// 请求方法封装
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const request = <T = any>(config: AxiosRequestConfig): Promise<T> => {
  return service.request(config) as unknown as Promise<T>
}

export default service
