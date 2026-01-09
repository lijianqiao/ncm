<script setup lang="ts">
import { ref, h } from 'vue'
import {
  type DataTableColumns,
  NTag,
  NDrawer,
  NDrawerContent,
  NDescriptions,
  NDescriptionsItem,
  type DropdownOption,
  NCode,
} from 'naive-ui'
import { getOperationLogs, type OperationLog, type LogSearchParams } from '@/api/logs'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import { formatDateTime } from '@/utils/date'

defineOptions({
  name: 'OperationLogs',
})

const tableRef = ref()

// Current selected log for details drawer
const currentLog = ref<OperationLog | null>(null)
const drawerVisible = ref(false)

const handleViewDetails = (row: OperationLog) => {
  currentLog.value = row
  drawerVisible.value = true
}

const contextMenuOptions: DropdownOption[] = [
  {
    label: '查看详情',
    key: 'details',
  },
]

const handleContextMenuSelect = (key: string | number, row: OperationLog) => {
  if (key === 'details') {
    handleViewDetails(row)
  }
}

const columns: DataTableColumns<OperationLog> = [
  { title: '操作人', key: 'username', width: 100, fixed: 'left' },
  {
    title: '模块',
    key: 'module',
    width: 120,
    fixed: 'left',
  },
  { title: '内容', key: 'summary', ellipsis: { tooltip: true } },
  {
    title: '方法',
    key: 'method',
    width: 100,
    render(row) {
      let type: 'default' | 'info' | 'success' | 'warning' | 'error' = 'default'
      switch (row.method) {
        case 'GET':
          type = 'info'
          break
        case 'POST':
          type = 'success'
          break
        case 'PUT':
          type = 'warning'
          break
        case 'DELETE':
          type = 'error'
          break
      }
      return h(NTag, { type, size: 'small' }, { default: () => row.method })
    },
  },
  { title: '路径', key: 'path', ellipsis: { tooltip: true } },
  {
    title: '参数',
    key: 'params',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => (row.params ? JSON.stringify(row.params) : ''),
  },
  {
    title: '响应',
    key: 'response_result',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => (row.response_result ? JSON.stringify(row.response_result) : ''),
  },
  {
    title: 'U/A',
    key: 'user_agent',
    width: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态码',
    key: 'response_code',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: row.response_code < 400 ? 'success' : 'error', size: 'small' },
        { default: () => row.response_code },
      )
    },
  },
  { title: 'IP地址', key: 'ip', width: 130 },
  {
    title: '耗时(s)',
    key: 'duration',
    width: 100,
    sorter: 'default',
    render: (row) => row.duration.toFixed(3),
  },
  {
    title: '操作时间',
    key: 'created_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.created_at),
  },
]

// Search Filters
const searchFilters: FilterConfig[] = []

const loadData = async (params: LogSearchParams) => {
  // ProTable passes flattened params

  const { page, page_size, keyword, sort } = params

  const res = await getOperationLogs({
    page,
    page_size,
    keyword,
    sort,
  })
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleReset = () => {}
</script>

<template>
  <div class="operation-logs p-4">
    <ProTable
      ref="tableRef"
      title="操作日志"
      :columns="columns"
      :request="loadData"
      :row-key="(row) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索操作人/IP/模块/操作内容/请求方法/路径"
      :search-filters="searchFilters"
      :scroll-x="1800"
      @context-menu-select="handleContextMenuSelect"
      @reset="handleReset"
    />

    <n-drawer v-model:show="drawerVisible" width="700" placement="right">
      <n-drawer-content title="审计详情">
        <n-descriptions
          :column="1"
          bordered
          label-placement="left"
          :label-style="{ 'white-space': 'nowrap', width: '120px' }"
          v-if="currentLog"
        >
          <n-descriptions-item label="ID">
            {{ currentLog.id }}
          </n-descriptions-item>
          <n-descriptions-item label="操作人">
            {{ currentLog.username }}
          </n-descriptions-item>
          <n-descriptions-item label="用户ID">
            {{ currentLog.user_id }}
          </n-descriptions-item>
          <n-descriptions-item label="IP地址">
            {{ currentLog.ip }}
          </n-descriptions-item>
          <n-descriptions-item label="模块">
            <n-tag>{{ currentLog.module }}</n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="操作内容">
            {{ currentLog.summary }}
          </n-descriptions-item>
          <n-descriptions-item label="请求方法">
            <n-tag type="info">{{ currentLog.method }}</n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="请求路径">
            <div style="word-break: break-all">{{ currentLog.path }}</div>
          </n-descriptions-item>
          <n-descriptions-item label="请求参数">
            <n-code :code="JSON.stringify(currentLog.params, null, 2)" language="json" word-wrap />
          </n-descriptions-item>
          <n-descriptions-item label="响应结果">
            <n-code
              :code="JSON.stringify(currentLog.response_result, null, 2)"
              language="json"
              word-wrap
            />
          </n-descriptions-item>
          <n-descriptions-item label="User Agent">
            {{ currentLog.user_agent }}
          </n-descriptions-item>
          <n-descriptions-item label="响应状态码">
            <n-tag :type="currentLog.response_code < 400 ? 'success' : 'error'">
              {{ currentLog.response_code }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="请求耗时">
            {{ currentLog.duration.toFixed(4) }} 秒
          </n-descriptions-item>
          <n-descriptions-item label="操作时间">
            {{ formatDateTime(currentLog.created_at) }}
          </n-descriptions-item>
        </n-descriptions>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}
</style>
