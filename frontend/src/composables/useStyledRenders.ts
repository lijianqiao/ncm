/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: useStyledRenders.ts
 * @DateTime: 2026-01-27
 * @Docs: 表格/详情页通用样式渲染工具
 */

import { h, type VNode } from 'vue'
import { NTag, NText, NTooltip, NIcon, NEllipsis } from 'naive-ui'
import { CopyOutline } from '@vicons/ionicons5'
import { $alert } from '@/utils/alert'
import {
  type TagType,
  HttpMethodColors,
  getStatusCodeColor,
  type HttpMethod,
} from '@/types/enum-labels'

/**
 * 渲染 IP 地址（等宽字体 + 可复制）
 */
export function renderIpAddress(ip: string | null | undefined): VNode {
  if (!ip) return h('span', { class: 'text-gray' }, '-')

  const copyIp = (e: Event) => {
    e.stopPropagation()
    navigator.clipboard.writeText(ip)
    $alert.success('IP 已复制')
  }

  return h(
    'span',
    {
      class: 'ip-address',
      style: {
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: '13px',
        backgroundColor: 'rgba(0, 0, 0, 0.04)',
        padding: '2px 6px',
        borderRadius: '4px',
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
      },
      onClick: copyIp,
      title: '点击复制',
    },
    [
      ip,
      h(NIcon, { size: 12, style: { opacity: 0.5 } }, { default: () => h(CopyOutline) }),
    ],
  )
}

/**
 * 渲染代码/标识符（等宽字体样式）
 */
export function renderCode(
  code: string | null | undefined,
  options?: { color?: string; copyable?: boolean },
): VNode {
  if (!code) return h('span', { class: 'text-gray' }, '-')

  const { color = 'rgba(64, 158, 255, 0.1)', copyable = false } = options || {}

  const handleCopy = (e: Event) => {
    if (!copyable) return
    e.stopPropagation()
    navigator.clipboard.writeText(code)
    $alert.success('已复制')
  }

  const codeStyle = {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: '12px',
    backgroundColor: color,
    padding: '2px 6px',
    borderRadius: '4px',
    color: '#476582',
    cursor: copyable ? 'pointer' : 'default',
    display: copyable ? 'inline-flex' : 'inline',
    alignItems: 'center',
    gap: '4px',
  }

  if (copyable) {
    return h(
      'code',
      {
        style: codeStyle,
        onClick: handleCopy,
        title: '点击复制',
      },
      [code, h(NIcon, { size: 12, style: { opacity: 0.5 } }, { default: () => h(CopyOutline) })],
    )
  }

  return h('code', { style: codeStyle }, code)
}

/**
 * 渲染 UUID（简短显示 + Tooltip 完整内容）
 */
export function renderUuid(uuid: string | null | undefined): VNode {
  if (!uuid) return h('span', { class: 'text-gray' }, '-')

  const shortId = uuid.slice(0, 8) + '...'

  return h(
    NTooltip,
    { trigger: 'hover' },
    {
      trigger: () =>
        h(
          'code',
          {
            style: {
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              fontSize: '12px',
              backgroundColor: 'rgba(0, 0, 0, 0.04)',
              padding: '2px 6px',
              borderRadius: '4px',
              cursor: 'pointer',
            },
            onClick: (e: Event) => {
              e.stopPropagation()
              navigator.clipboard.writeText(uuid)
              $alert.success('ID 已复制')
            },
          },
          shortId,
        ),
      default: () => uuid,
    },
  )
}

/**
 * 渲染 HTTP 方法标签
 */
export function renderHttpMethod(method: string | null | undefined): VNode {
  if (!method) return h('span', { class: 'text-gray' }, '-')

  const upperMethod = method.toUpperCase() as HttpMethod
  const tagType = HttpMethodColors[upperMethod] || 'default'

  return h(
    NTag,
    {
      type: tagType,
      size: 'small',
      bordered: false,
      style: { fontWeight: 500 },
    },
    { default: () => upperMethod },
  )
}

/**
 * 渲染 HTTP 状态码
 */
export function renderStatusCode(code: number | null | undefined): VNode {
  if (code === null || code === undefined) return h('span', { class: 'text-gray' }, '-')

  const tagType = getStatusCodeColor(code)

  return h(
    NTag,
    {
      type: tagType,
      size: 'small',
      bordered: false,
      round: true,
    },
    { default: () => code },
  )
}

/**
 * 渲染模块/标签（带背景色的标签）
 */
export function renderModule(module: string | null | undefined): VNode {
  if (!module) return h('span', { class: 'text-gray' }, '-')

  return h(
    NTag,
    {
      type: 'info',
      size: 'small',
      bordered: false,
    },
    { default: () => module },
  )
}

/**
 * 渲染布尔状态标签
 */
export function renderBooleanStatus(
  value: boolean | null | undefined,
  options?: { trueText?: string; falseText?: string },
): VNode {
  const { trueText = '成功', falseText = '失败' } = options || {}

  if (value === null || value === undefined) return h('span', { class: 'text-gray' }, '-')

  return h(
    NTag,
    {
      type: value ? 'success' : 'error',
      size: 'small',
      bordered: false,
    },
    { default: () => (value ? trueText : falseText) },
  )
}

/**
 * 渲染路径（等宽 + 省略）
 */
export function renderPath(path: string | null | undefined, maxWidth = 200): VNode {
  if (!path) return h('span', { class: 'text-gray' }, '-')

  return h(
    NEllipsis,
    { style: { maxWidth: `${maxWidth}px` } },
    {
      default: () =>
        h(
          'code',
          {
            style: {
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              fontSize: '12px',
              color: '#476582',
            },
          },
          path,
        ),
    },
  )
}

/**
 * 渲染耗时（毫秒）
 */
export function renderDuration(ms: number | null | undefined): VNode {
  if (ms === null || ms === undefined) return h('span', { class: 'text-gray' }, '-')

  // 根据耗时长度显示不同颜色
  let color = '#18a058' // 绿色 - 快速
  if (ms > 1000) color = '#f0a020' // 黄色 - 较慢
  if (ms > 3000) color = '#d03050' // 红色 - 很慢

  return h(
    'span',
    {
      style: {
        color,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: '13px',
      },
    },
    `${ms.toFixed(2)} ms`,
  )
}

/**
 * 渲染 User-Agent（简短显示）
 */
export function renderUserAgent(ua: string | null | undefined): VNode {
  if (!ua) return h('span', { class: 'text-gray' }, '-')

  // 提取浏览器和系统信息
  const browserMatch = ua.match(/(Chrome|Firefox|Safari|Edge|Opera)[\/\s](\d+)/i)
  const osMatch = ua.match(/(Windows|Mac OS|Linux|Android|iOS)[^\);]*/i)

  const browser = browserMatch ? `${browserMatch[1]} ${browserMatch[2]}` : '未知浏览器'
  const os = osMatch ? osMatch[0].trim() : '未知系统'

  return h(
    NTooltip,
    { trigger: 'hover', style: { maxWidth: '400px' } },
    {
      trigger: () =>
        h(
          NText,
          { depth: 2, style: { fontSize: '13px' } },
          { default: () => `${browser} / ${os}` },
        ),
      default: () => h('div', { style: { wordBreak: 'break-all' } }, ua),
    },
  )
}

/**
 * 通用枚举标签渲染
 */
export function renderEnumTag<T extends string>(
  value: T | null | undefined,
  labels: Record<T, string>,
  colors: Record<T, TagType>,
): VNode {
  if (!value) return h('span', { class: 'text-gray' }, '-')

  return h(
    NTag,
    {
      type: colors[value] || 'default',
      size: 'small',
      bordered: false,
    },
    { default: () => labels[value] || value },
  )
}
