<script setup lang="ts">
/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: index.vue
 * @DateTime: 2026-01-08
 * @Docs: 在线会话管理页面
 */

import { ref, h } from 'vue'
import {
  type DataTableColumns,
  NButton,
  NPopconfirm,
  useDialog,
  type DropdownOption,
  NEllipsis,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getOnlineSessions,
  kickUser,
  batchKickUsers,
  type OnlineSession,
  type SessionSearchParams,
} from '@/api/sessions'
import { formatDateTime } from '@/utils/date'
import ProTable from '@/components/common/ProTable.vue'

defineOptions({
  name: 'OnlineSessions',
})

const dialog = useDialog()
const tableRef = ref()

// 列定义 - 根据实际 API 响应调整
const columns: DataTableColumns<OnlineSession> = [
  { type: 'selection', fixed: 'left' },
  { title: '用户名', key: 'username', width: 120, fixed: 'left' },
  { title: 'IP地址', key: 'ip', width: 140 },
  {
    title: 'User Agent',
    key: 'user_agent',
    width: 300,
    ellipsis: { tooltip: true },
    render: (row) => h(NEllipsis, { style: 'max-width: 280px' }, { default: () => row.user_agent }),
  },
  {
    title: '登录时间',
    key: 'login_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.login_at),
  },
  {
    title: '最后活跃',
    key: 'last_seen_at',
    width: 180,
    render: (row) => formatDateTime(row.last_seen_at),
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render(row) {
      return h(
        NPopconfirm,
        {
          onPositiveClick: () => handleKick(row),
        },
        {
          trigger: () =>
            h(
              NButton,
              { size: 'small', type: 'error', quaternary: true },
              { default: () => '强制下线' },
            ),
          default: () => `确定要将用户 "${row.username}" 强制下线吗？`,
        },
      )
    },
  },
]

// 右键菜单
const contextMenuOptions: DropdownOption[] = [{ label: '强制下线', key: 'kick' }]

const handleContextMenuSelect = (key: string | number, row: OnlineSession) => {
  if (key === 'kick') {
    dialog.warning({
      title: '确认操作',
      content: `确定要将用户 "${row.username}" 强制下线吗？`,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: () => handleKick(row),
    })
  }
}

// 单个踢人
const handleKick = async (row: OnlineSession) => {
  try {
    await kickUser(row.user_id)
    $alert.success(`已将用户 "${row.username}" 强制下线`)
    tableRef.value?.refresh()
  } catch {
    // 错误由 request.ts 统一处理
  }
}

// 批量踢人 - 使用 ProTable 的 batch-delete 事件
const handleBatchKick = async (keys: Array<string | number>) => {
  if (keys.length === 0) {
    $alert.warning('请先选择要下线的用户')
    return
  }

  dialog.warning({
    title: '批量强制下线',
    content: `确定要将选中的 ${keys.length} 个用户强制下线吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const userIds = keys.map((k) => String(k))
        const res = await batchKickUsers(userIds)
        const result = res.data
        if (result) {
          $alert.success(`成功下线 ${result.success_count} 个用户`)
          if (result.failed_ids && result.failed_ids.length > 0) {
            $alert.warning(`${result.failed_ids.length} 个用户下线失败`)
          }
        }
        tableRef.value?.refresh()
      } catch {
        // 错误由 request.ts 统一处理
      }
    },
  })
}

// 加载数据
const loadData = async (params: SessionSearchParams) => {
  const res = await getOnlineSessions(params)
  return {
    data: res.data.items || [],
    total: res.data.total || 0,
  }
}
</script>

<template>
  <div class="online-sessions p-4">
    <ProTable
      ref="tableRef"
      title="在线会话"
      :columns="columns"
      :request="loadData"
      :row-key="(row) => row.user_id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/IP"
      :scroll-x="1200"
      show-batch-delete
      @context-menu-select="handleContextMenuSelect"
      @batch-delete="handleBatchKick"
    />
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}

.online-sessions {
  height: 100%;
}
</style>
