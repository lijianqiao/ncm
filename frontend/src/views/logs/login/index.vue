<script setup lang="ts">
import { h, ref } from 'vue'
import { NTag, type DataTableColumns } from 'naive-ui'
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
  { title: '消息', key: 'msg', minWidth: 220, ellipsis: { tooltip: true } },
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
      search-placeholder="搜索用户名/IP/消息"
      :scroll-x="1200"
    />
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}
</style>

