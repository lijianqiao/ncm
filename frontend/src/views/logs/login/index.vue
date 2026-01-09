<script setup lang="ts">
import { ref, h } from 'vue'
import {
  type DataTableColumns,
  NTag,
  // NTag, // NTag moved to a separate import
  NDrawer,
  NDrawerContent,
  NDescriptions,
  NDescriptionsItem,
  type DropdownOption,
} from 'naive-ui'
import { getLoginLogs, type LoginLog, type LogSearchParams } from '@/api/logs'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import { formatDateTime } from '@/utils/date'

defineOptions({
  name: 'LoginLogs',
})

const tableRef = ref()

// Current selected log for details drawer
const currentLog = ref<LoginLog | null>(null)
const drawerVisible = ref(false)

const handleViewDetails = (row: LoginLog) => {
  currentLog.value = row
  drawerVisible.value = true
}

const contextMenuOptions: DropdownOption[] = [
  {
    label: '查看详情',
    key: 'details',
  },
]

const handleContextMenuSelect = (key: string | number, row: LoginLog) => {
  if (key === 'details') {
    handleViewDetails(row)
  }
}

const columns: DataTableColumns<LoginLog> = [
  { title: '用户名', key: 'username', width: 120 },
  { title: 'IP地址', key: 'ip', width: 140 },
  { title: '浏览', key: 'browser', width: 200 },
  {
    title: '操作系统',
    key: 'os',
    width: 200,
  },
  { title: '设备', key: 'device', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render(row) {
      return h(
        NTag,
        { type: row.status ? 'success' : 'error', size: 'small' },
        { default: () => (row.status ? '成功' : '失败') },
      )
    },
  },
  { title: '提示信息', key: 'msg', width: 200 },
  {
    title: '登录时间',
    key: 'created_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.created_at),
  },
]

// Search Filters
const searchFilters: FilterConfig[] = []

const loadData = async (params: LogSearchParams) => {
  // ProTable passes keyword and flattened filters directly in params

  const { page, page_size, keyword, sort } = params

  const res = await getLoginLogs({
    page,
    page_size,
    keyword, // Use keyword from ProTable
    sort,
  })
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleReset = () => {
  // ProTable handles keyword reset internally, or via emit('reset') we can do extra logic
}
</script>

<template>
  <div class="login-logs p-4">
    <ProTable
      ref="tableRef"
      title="登录日志"
      :columns="columns"
      :request="loadData"
      :row-key="(row) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/IP/提示信息/浏览器/操作系统/设备"
      :search-filters="searchFilters"
      @context-menu-select="handleContextMenuSelect"
      @reset="handleReset"
    />

    <n-drawer v-model:show="drawerVisible" width="500" placement="right">
      <n-drawer-content title="登录详情">
        <n-descriptions :column="1" bordered label-placement="left" v-if="currentLog">
          <n-descriptions-item label="ID">
            {{ currentLog.id }}
          </n-descriptions-item>
          <n-descriptions-item label="用户名">
            {{ currentLog.username }}
          </n-descriptions-item>
          <n-descriptions-item label="IP地址">
            {{ currentLog.ip }}
          </n-descriptions-item>
          <n-descriptions-item label="User Agent">
            {{ currentLog.user_agent }}
          </n-descriptions-item>
          <n-descriptions-item label="浏览器">
            {{ currentLog.browser }}
          </n-descriptions-item>
          <n-descriptions-item label="操作系统">
            {{ currentLog.os }}
          </n-descriptions-item>
          <n-descriptions-item label="设备">
            {{ currentLog.device }}
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="currentLog.status ? 'success' : 'error'">
              {{ currentLog.status ? '成功' : '失败' }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="提示信息">
            {{ currentLog.msg }}
          </n-descriptions-item>
          <n-descriptions-item label="登录时间">
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
