/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: useDeptTree.ts
 * @DateTime: 2026-01-12
 * @Docs: 部门树数据获取 Composable
 */

import { ref } from 'vue'
import { getDeptTree } from '@/api/depts'

/**
 * 树形选择器选项接口
 */
export interface TreeSelectOption {
    label: string
    key: string
    children?: TreeSelectOption[]
}

/**
 * 部门数据接口
 */
interface Dept {
    id: string
    name: string
    children?: Dept[]
}

/**
 * 部门树数据获取 Composable
 *
 * 提供部门树数据的获取和转换功能，支持缓存以避免重复请求。
 *
 * @param options 配置选项
 * @returns 部门树数据和获取方法
 *
 * @example
 * ```ts
 * const { deptTreeOptions, loading, fetchDeptTree } = useDeptTree()
 *
 * // 获取部门树（支持缓存）
 * await fetchDeptTree()
 *
 * // 强制刷新
 * await fetchDeptTree(true)
 * ```
 */
export function useDeptTree(options: { cacheTTL?: number } = {}) {
    const { cacheTTL = 60000 } = options // 默认缓存 1 分钟

    const deptTreeOptions = ref<TreeSelectOption[]>([])
    const loading = ref(false)
    let lastFetchTime = 0

    /**
     * 将部门数据转换为树形选择器选项
     */
    const transformToTreeOptions = (items: Dept[]): TreeSelectOption[] => {
        return items.map((item) => ({
            label: item.name,
            key: item.id,
            children: item.children?.length ? transformToTreeOptions(item.children) : undefined,
        }))
    }

    /**
     * 获取部门树数据
     * @param force 是否强制刷新（忽略缓存）
     */
    const fetchDeptTree = async (force = false): Promise<TreeSelectOption[]> => {
        // 检查缓存是否有效
        if (!force && Date.now() - lastFetchTime < cacheTTL && deptTreeOptions.value.length > 0) {
            return deptTreeOptions.value
        }

        loading.value = true
        try {
            const res = await getDeptTree()
            deptTreeOptions.value = transformToTreeOptions(res.data || [])
            lastFetchTime = Date.now()
            return deptTreeOptions.value
        } catch {
            // 错误由全局拦截器处理
            return []
        } finally {
            loading.value = false
        }
    }

    /**
     * 清除缓存
     */
    const clearCache = () => {
        lastFetchTime = 0
    }

    return {
        /** 部门树选项数据 */
        deptTreeOptions,
        /** 是否正在加载 */
        loading,
        /** 获取部门树数据 */
        fetchDeptTree,
        /** 清除缓存 */
        clearCache,
    }
}
