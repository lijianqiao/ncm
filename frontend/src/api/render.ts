/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: render.ts
 * @DateTime: 2026-01-12
 * @Docs: 模板渲染预览(Dry-Run) API 模块
 */

import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

export interface RenderRequest {
    params: Record<string, unknown>
    device_id?: string
}

export interface RenderResponse {
    rendered: string
}

/** 模板渲染预览(Dry-Run) */
export function renderTemplate(templateId: string, data: RenderRequest) {
    return request<ResponseBase<RenderResponse>>({
        url: `/render/template/${templateId}`,
        method: 'post',
        data,
    })
}
