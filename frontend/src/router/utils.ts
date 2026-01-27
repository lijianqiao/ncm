/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: utils.ts
 * @DateTime: 2026-01-08
 * @Docs: 动态路由生成工具
 */

import type { RouteRecordRaw, RouteComponent } from 'vue-router'
import type { Menu } from '@/api/menus'

// Glob 导入所有视图组件，用于动态路由匹配
const modules = import.meta.glob('@/views/**/*.vue')

/**
 * 规范化组件路径
 * 支持多种格式：
 *   - /views/ncm/devices/index.vue (标准格式)
 *   - ncm/devices/index (简写格式)
 *   - /views/ncm/devices/index (无后缀)
 */
function normalizeComponentPath(componentPath: string): string {
  let path = componentPath

  // 如果不以 /views 开头，添加 /views/ 前缀
  if (!path.startsWith('/views')) {
    path = '/views/' + path.replace(/^\//, '')
  }

  // 如果不以 .vue 结尾，添加 .vue 后缀
  if (!path.endsWith('.vue')) {
    path = path + '.vue'
  }

  return '/src' + path
}

/**
 * 根据后端菜单数据生成 Vue Router 路由配置
 * @param menus 后端返回的菜单列表
 * @returns RouteRecordRaw 数组
 */
export function generateRoutes(menus: Menu[]): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = []

  for (const menu of menus) {
    // 跳过权限点类型（不生成路由）
    if (menu.type === 'PERMISSION') continue

    // 解析组件
    let component: RouteComponent | (() => Promise<RouteComponent>) | undefined

    if (menu.component?.toUpperCase() === 'LAYOUT') {
      // Layout 类型映射到透传组件
      component = () => import('@/layouts/RouterView.vue')
    } else if (menu.component) {
      const key = normalizeComponentPath(menu.component)
      if (modules[key]) {
        component = modules[key] as () => Promise<RouteComponent>
      } else {
        // 组件路径不存在，显示 404
        component = () => import('@/views/error/404.vue')
      }
    } else if (menu.type === 'CATALOG' || (menu.children && menu.children.length > 0)) {
      // 目录/父菜单未配置组件时，使用 RouterView 承载子路由
      component = () => import('@/layouts/RouterView.vue')
    } else if (menu.type === 'MENU') {
      // 菜单类型但没有组件路径，显示 404
      component = () => import('@/views/error/404.vue')
    }

    const route: RouteRecordRaw = {
      path: menu.path,
      name: menu.name,
      component: component,
      meta: {
        title: menu.title,
        icon: menu.icon,
        is_hidden: menu.is_hidden,
        permission: menu.permission,
        sort: menu.sort,
      },
      children: [],
    }

    if (menu.children && menu.children.length > 0) {
      route.children = generateRoutes(menu.children)
    }
    routes.push(route)
  }

  return routes
}
