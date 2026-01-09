import { request } from '@/utils/request'
import type { ResponseBase } from '@/types/api'

export interface PermissionDictItem {
  code: string
  message: string
  data: Array<{
    code: string
    name: string
    description: string
  }>
}

// 根据用户请求描述保持简单。
// 用户说响应是“ResponseBase[list[PermissionDictItem]]”，但表显示响应中的数据数组。
// 我们假设标准 ResponseBase<T> 结构，其中 T 是数据有效负载。
// 基于“ResponseBase[list[PermissionDictItem]]”，T 是 PermissionDictItem[]。
// 然而，用户提供的表格显示：代码、消息、数据（数组）。
// 这表明 API 返回标准结构，并且“数据”字段包含列表。
// 让我们定义项目类型。

export interface PermissionItem {
  code: string
  name: string // This might be missing or different based on common rbac, but user mentions 'code/name/description'
  description: string
}

export function getPermissionDict() {
  return request<ResponseBase<PermissionItem[]>>({
    url: '/permissions/', // User specified /api/v1/permissions/, request util handles prefix usually? Let's check api/menus.ts
    method: 'get',
  })
}
