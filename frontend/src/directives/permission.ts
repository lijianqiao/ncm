import { useUserStore } from '@/stores/user'
import type { Directive, DirectiveBinding } from 'vue'

export const permission: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    const userStore = useUserStore()
    const permissions = userStore.permissions

    if (value && value instanceof Array && value.length > 0) {
      const permissionRoles = value

      const hasPermission = permissions.some((perm: string) => {
        return permissionRoles.includes(perm) || perm === '*:*:*'
      })

      if (!hasPermission) {
        if (el.parentNode) {
          el.parentNode.removeChild(el)
        }
      }
    } else {
      throw new Error(`need roles! Like v-permission="['sys:user:add','sys:user:edit']"`)
    }
  },
}
