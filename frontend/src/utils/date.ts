/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: date.ts
 * @DateTime: 2026-01-08
 * @Docs: 日期时间格式化工具
 */

import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

// 从环境变量读取时区配置，默认 Asia/Shanghai
const DEFAULT_TIMEZONE = import.meta.env.VITE_TIMEZONE || 'Asia/Shanghai'

/**
 * 格式化日期时间
 * @param date 日期字符串
 * @param format 格式化模板，默认 'YYYY-MM-DD HH:mm:ss'
 * @param tz 时区，默认使用环境变量配置
 * @returns 格式化后的日期字符串
 */
export function formatDateTime(
  date: string | null | undefined,
  format = 'YYYY-MM-DD HH:mm:ss',
  tz = DEFAULT_TIMEZONE,
): string {
  if (!date) return 'N/A'
  return dayjs(date).tz(tz).format(format)
}
