import { useUserStore } from '@/stores/user'
import type { Directive, DirectiveBinding } from 'vue'

/**
 * 检查权限并控制元素显隐
 */
function checkPermission(el: HTMLElement, binding: DirectiveBinding): void {
  const { value } = binding
  const userStore = useUserStore()
  const permissions = userStore.permissions

  // 支持字符串和数组两种格式
  const requiredPerms = Array.isArray(value) ? value : [value]

  if (!requiredPerms.length || !requiredPerms[0]) {
    console.warn('[v-permission] 需要传入权限标识，如 v-permission="[\'sys:user:add\']"')
    return
  }

  const hasPermission = permissions.some((perm: string) => {
    return requiredPerms.includes(perm) || perm === '*:*:*'
  })

  // 使用 display 控制显隐，而非删除 DOM，便于动态权限变更时恢复
  el.style.display = hasPermission ? '' : 'none'
}

export const permission: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    checkPermission(el, binding)
  },
  updated(el: HTMLElement, binding: DirectiveBinding) {
    checkPermission(el, binding)
  },
}
