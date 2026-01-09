/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: cookie.ts
 * @DateTime: 2026-01-08
 * @Docs: Cookie 工具函数
 */

/**
 * 从 document.cookie 中读取指定 Cookie 的值
 * @param name Cookie 名称
 * @returns Cookie 值，不存在则返回 null
 */
export function getCookie(name: string): string | null {
  const matches = document.cookie.match(
    new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'),
  )
  return matches && matches[1] ? decodeURIComponent(matches[1]) : null
}

/**
 * 获取 CSRF Token（从 Cookie 读取）
 * @returns CSRF Token 值
 */
export function getCsrfToken(): string | null {
  return getCookie('csrf_token')
}
