/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: index.ts
 * @DateTime: 2026-01-08
 * @Docs: 路由配置与守卫，适配 HttpOnly Cookie 认证方案
 */

import { createRouter, createWebHistory } from 'vue-router'
import { createDiscreteApi } from 'naive-ui'
import { $alert } from '@/utils/alert'
import { useUserStore } from '@/stores/user'
import { getAccessToken } from '@/utils/request'

const { loadingBar } = createDiscreteApi(['loadingBar'])

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/index.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/',
      name: 'MainLayout',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        // 动态路由会在这里添加
      ],
    },
    {
      path: '/403',
      name: 'Forbidden',
      component: () => import('@/views/error/403.vue'),
      meta: { title: '403 Forbidden' },
    },
    {
      path: '/500',
      name: 'ServerError',
      component: () => import('@/views/error/500.vue'),
      meta: { title: '500 Server Error' },
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  loadingBar.start()
  const userStore = useUserStore()

  // 从内存获取 Token
  let hasToken = !!getAccessToken()

  // 页面刷新时尝试使用 Refresh Token 恢复登录状态
  if (!hasToken && to.name !== 'Login') {
    const refreshed = await userStore.initialTokenRefresh()
    if (refreshed) {
      hasToken = true
    }
  }

  // 未登录且不是登录页，跳转登录
  if (to.name !== 'Login' && !hasToken) {
    $alert.error('请先登录')
    next({ name: 'Login' })
    return
  }

  // 已登录但没有用户信息，获取用户信息
  if (hasToken && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo()
    } catch {
      userStore.logout()
      next({ name: 'Login' })
      return
    }
  }

  // 动态路由加载
  if (hasToken && !userStore.isRoutesLoaded) {
    try {
      const { routes } = await userStore.fetchUserMenus()

      // 添加动态路由到 MainLayout
      routes.forEach((route) => {
        router.addRoute('MainLayout', route)
      })

      // 添加 404 兜底路由（先检查是否已存在，避免重复添加）
      if (!router.hasRoute('NotFound')) {
        router.addRoute({
          path: '/:pathMatch(.*)*',
          name: 'NotFound',
          component: () => import('@/views/error/404.vue'),
          meta: { title: '404 Not Found' },
        })
      }

      // 重新导航以使路由生效
      next({ ...to, replace: true })
      return
    } catch {
      // 错误由 request.ts 统一处理
      userStore.logout()
      return
    }
  }

  // 已登录用户访问登录页，跳转到首页
  if (to.name === 'Login' && hasToken) {
    next({ path: userStore.homePath || '/dashboard' })
    return
  }

  // 根路径跳转到 dashboard
  if (hasToken && to.path === '/') {
    next({ path: userStore.homePath || '/dashboard' })
    return
  }

  // 权限检查
  if (hasToken && to.meta.permission) {
    const requiredPerm = to.meta.permission as string
    const isSuperuser = userStore.userInfo?.is_superuser

    const hasPerm =
      isSuperuser ||
      userStore.permissions.includes(requiredPerm) ||
      userStore.permissions.includes('*:*:*') ||
      userStore.hasMenu(to.name as string)

    if (!hasPerm) {
      $alert.warning('无权访问')
      next({ name: 'Forbidden' })
      loadingBar.error()
      return
    }
  }

  next()
})

router.afterEach((to) => {
  loadingBar.finish()
  if (to.meta.title) {
    const title = import.meta.env.VITE_SITE_TITLE || 'Admin RBAC'
    document.title = `${to.meta.title as string} - ${title}`
  }
})

export default router
