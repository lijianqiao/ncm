/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: user.ts
 * @DateTime: 2026-01-08
 * @Docs: 用户状态管理 Store，支持 HttpOnly Cookie 认证方案
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUserInfo, logout as logoutApi } from '@/api/auth'
import { getMyMenus, type Menu } from '@/api/menus'
import type { User } from '@/api/users'
import { generateRoutes } from '@/router/utils'
import { getAccessToken, setAccessToken, clearAccessToken } from '@/utils/request'
import { getCsrfToken } from '@/utils/cookie'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  // Token 现在存储在 request.ts 的内存变量中
  // 这里只保留一个响应式引用用于UI判断
  const isLoggedIn = ref(!!getAccessToken())
  const userInfo = ref<User | null>(null)
  const permissions = ref<string[]>([])
  const userMenus = ref<Menu[]>([])
  const isRoutesLoaded = ref(false)

  /**
   * 登录成功后设置 Token
   * Access Token 存入内存，Refresh Token 由浏览器自动从 Set-Cookie 保存
   */
  function setToken(accessToken: string) {
    setAccessToken(accessToken)
    isLoggedIn.value = true
  }

  /**
   * 清除所有认证状态
   */
  function clearAuth() {
    clearAccessToken()
    isLoggedIn.value = false
    userInfo.value = null
    permissions.value = []
    userMenus.value = []
    isRoutesLoaded.value = false
  }

  function setUserInfo(info: User) {
    userInfo.value = info
  }

  function setPermissions(perms: string[]) {
    permissions.value = perms
  }

  /**
   * 尝试使用 Refresh Token 刷新 Access Token
   * 用于页面刷新后恢复登录状态
   */
  async function initialTokenRefresh(): Promise<boolean> {
    // 检查 CSRF Token 是否存在（表示可能有有效的 Refresh Token Cookie）
    const csrfToken = getCsrfToken()
    if (!csrfToken) {
      return false
    }

    try {
      const response = await axios.post(
        `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/refresh`,
        {},
        {
          withCredentials: true,
          headers: {
            'X-CSRF-Token': csrfToken,
          },
        },
      )

      const accessToken = response.data?.access_token
      if (accessToken) {
        setToken(accessToken)
        return true
      }
      return false
    } catch {
      clearAuth()
      return false
    }
  }

  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      const data = res.data
      userInfo.value = data
      if (data.permissions) {
        permissions.value = data.permissions
      }
      return res.data
    } catch (error) {
      clearAuth()
      throw error
    }
  }

  async function fetchUserMenus() {
    try {
      const res = await getMyMenus()
      if (res.data) {
        userMenus.value = res.data

        // 从菜单中提取权限标识
        const perms: string[] = []
        const extractPermissions = (menus: Menu[]) => {
          menus.forEach((menu) => {
            if (menu.permission) {
              perms.push(menu.permission)
            }
            if (menu.children && menu.children.length > 0) {
              extractPermissions(menu.children)
            }
          })
        }
        extractPermissions(res.data)

        // 合并权限，去重
        const uniquePerms = Array.from(new Set([...permissions.value, ...perms]))
        permissions.value = uniquePerms
      }

      // 生成动态路由
      const routes = generateRoutes(res.data || [])
      isRoutesLoaded.value = true

      return { menus: res.data, routes }
    } catch (error) {
      console.error('获取用户菜单失败', error)
      return { menus: [], routes: [] }
    }
  }

  /**
   * 退出登录
   * 调用后端 logout 接口，后端会清理 Cookie
   */
  async function logout() {
    try {
      await logoutApi()
    } catch (error) {
      console.error('退出登录失败:', error)
    } finally {
      clearAuth()
      window.location.href = '/login'
    }
  }

  function hasMenu(routeName: string): boolean {
    const checkMenu = (menus: Menu[]): boolean => {
      for (const menu of menus) {
        if (menu.name === routeName) return true
        if (menu.children && menu.children.length > 0) {
          if (checkMenu(menu.children)) return true
        }
      }
      return false
    }
    return checkMenu(userMenus.value)
  }

  /**
   * 检查是否有有效的认证状态
   */
  function hasValidAuth(): boolean {
    return !!getAccessToken()
  }

  return {
    // 状态
    isLoggedIn,
    userInfo,
    permissions,
    userMenus,
    isRoutesLoaded,
    // 方法
    setToken,
    clearAuth,
    setUserInfo,
    setPermissions,
    initialTokenRefresh,
    fetchUserInfo,
    fetchUserMenus,
    logout,
    hasMenu,
    hasValidAuth,
    // 兼容旧代码的别名
    clearToken: clearAuth,
    token: isLoggedIn, // 兼容性
  }
})
