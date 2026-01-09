/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: auth.ts
 * @DateTime: 2026-01-08
 * @Docs: 认证相关 API，适配 HttpOnly Cookie 方案
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'
import type { User } from '@/api/users'

export interface LoginParams {
  username: string
  password: string
}

/**
 * 登录响应
 * 注意：新方案下只返回 access_token，refresh_token 通过 HttpOnly Cookie 设置
 */
export interface LoginResult {
  access_token: string
  token_type: string
}

/**
 * 用户登录
 * OAuth2 密码模式，使用 x-www-form-urlencoded 格式
 */
export function login(data: LoginParams) {
  const params = new URLSearchParams()
  params.append('username', data.username)
  params.append('password', data.password)

  return request<LoginResult>({
    url: '/auth/login',
    method: 'post',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    data: params,
  })
}

/**
 * 获取当前用户信息
 */
export function getUserInfo() {
  return request<ResponseBase<User>>({
    url: '/users/me',
    method: 'get',
  })
}

/**
 * 刷新 Token
 * 注意：新方案下不需要传递 refresh_token，它在 HttpOnly Cookie 中自动发送
 * 需要在请求头中带上 X-CSRF-Token
 *
 * 这个函数一般不直接调用，由 request.ts 中的拦截器自动处理
 */
export function refreshToken() {
  // 此函数保留用于类型兼容，实际刷新逻辑在 request.ts 中实现
  // 因为需要特殊处理 CSRF Token 和避免循环依赖
  return Promise.reject(new Error('请使用 request.ts 中的 doRefreshToken'))
}

/**
 * 更新当前用户信息
 */
export function updateCurrentUser(data: Partial<User>) {
  return request<ResponseBase<User>>({
    url: '/users/me',
    method: 'put',
    data,
  })
}

export interface ChangePasswordParams {
  old_password: string
  new_password: string
}

/**
 * 修改密码
 */
export function changePassword(data: ChangePasswordParams) {
  return request<ResponseBase<User>>({
    url: '/users/me/password',
    method: 'put',
    data,
  })
}

/**
 * 退出登录
 * 需要带 Authorization 头，后端会清理 Cookie
 */
export function logout() {
  return request<ResponseBase<void>>({
    url: '/auth/logout',
    method: 'post',
  })
}
