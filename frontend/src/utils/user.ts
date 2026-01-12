/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: user.ts
 * @DateTime: 2026-01-12
 * @Docs: 用户展示名格式化工具
 */

export function formatUserDisplayNameParts(
    nickname: string | null | undefined,
    username: string | null | undefined,
    fallback?: string | null | undefined,
): string {
    const nick = (nickname || '').trim()
    const user = (username || '').trim()
    if (nick && user) return `${nick}(${user})`
    return nick || user || fallback || '-'
}

export function formatUserDisplayName(
    user:
        | {
            nickname?: string | null
            username?: string | null
            id?: string | null
        }
        | null
        | undefined,
): string {
    if (!user) return '-'
    return formatUserDisplayNameParts(user.nickname, user.username, user.id)
}
