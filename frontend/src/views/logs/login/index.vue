<script setup lang="ts">
import { h, ref } from 'vue'
import { NDrawer, NDrawerContent, NDescriptions, NDescriptionsItem, NTag, type DataTableColumns, type DropdownOption } from 'naive-ui'
import { getLoginLogs, type LoginLog, type LogSearchParams } from '@/api/logs'
import { formatDateTime } from '@/utils/date'
import ProTable from '@/components/common/ProTable.vue'

defineOptions({
  name: 'LoginLog',
})

const tableRef = ref()

const columns: DataTableColumns<LoginLog> = [
  { title: '用户名', key: 'username', width: 140, sorter: 'default' },
  { title: 'IP', key: 'ip', width: 140 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: row.status ? 'success' : 'error', bordered: false },
        { default: () => (row.status ? '成功' : '失败') },
      )
    },
  },
  { title: '消息', key: 'msg', width: 220, ellipsis: { tooltip: true } },
  { title: '浏览器', key: 'browser', width: 160, ellipsis: { tooltip: true } },
  { title: '系统', key: 'os', width: 160, ellipsis: { tooltip: true } },
  { title: '设备', key: 'device', width: 140, ellipsis: { tooltip: true } },
  {
    title: '时间',
    key: 'created_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.created_at),
  },
]

// 右键菜单
const contextMenuOptions: DropdownOption[] = [{ label: '查看详情', key: 'detail' }]

// 抽屉状态
const showDrawer = ref(false)
const currentLog = ref<LoginLog | null>(null)

const handleContextMenuSelect = (key: string | number, row: LoginLog) => {
  if (key === 'detail') {
    currentLog.value = row
    showDrawer.value = true
  }
}

const loadData = async (params: LogSearchParams) => {
  const res = await getLoginLogs(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}
</script>

<template>
  <div class="p-4">
    <ProTable
      ref="tableRef"
      title="登录日志"
      :columns="columns"
      :request="loadData"
      :row-key="(row: LoginLog) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/IP/消息"
      @context-menu-select="handleContextMenuSelect"
    />

    <!-- 详情抽屉 -->
    <n-drawer v-model:show="showDrawer" :width="500" placement="right" :native-scrollbar="true">
      <n-drawer-content title="登录日志详情" closable>
        <n-descriptions v-if="currentLog" label-placement="left" :column="1" bordered>
          <n-descriptions-item label="ID">{{ currentLog.id }}</n-descriptions-item>
          <n-descriptions-item label="用户ID">{{ currentLog.user_id || '-' }}</n-descriptions-item>
          <n-descriptions-item label="用户名">{{ currentLog.username }}</n-descriptions-item>
          <n-descriptions-item label="IP">{{ currentLog.ip }}</n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="currentLog.status ? 'success' : 'error'" size="small">
              {{ currentLog.status ? '成功' : '失败' }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="消息">{{ currentLog.msg || '-' }}</n-descriptions-item>
          <n-descriptions-item label="浏览器">{{ currentLog.browser || '-' }}</n-descriptions-item>
          <n-descriptions-item label="系统">{{ currentLog.os || '-' }}</n-descriptions-item>
          <n-descriptions-item label="设备">{{ currentLog.device || '-' }}</n-descriptions-item>
          <n-descriptions-item label="时间">{{ formatDateTime(currentLog.created_at) }}</n-descriptions-item>
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
