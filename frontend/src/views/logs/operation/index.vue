<script setup lang="ts">
import { ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { getOperationLogs, type LogSearchParams, type OperationLog } from '@/api/logs'
import { formatDateTime } from '@/utils/date'
import ProTable from '@/components/common/ProTable.vue'

defineOptions({
  name: 'OperationLog',
})

const tableRef = ref()

const columns: DataTableColumns<OperationLog> = [
  { title: '用户名', key: 'username', width: 140, sorter: 'default' },
  { title: 'IP', key: 'ip', width: 140 },
  { title: '模块', key: 'module', width: 160, ellipsis: { tooltip: true } },
  { title: '摘要', key: 'summary', minWidth: 220, ellipsis: { tooltip: true } },
  { title: '方法', key: 'method', width: 90 },
  { title: '路径', key: 'path', minWidth: 220, ellipsis: { tooltip: true } },
  { title: '状态码', key: 'response_code', width: 100, sorter: 'default' },
  { title: '耗时(ms)', key: 'duration', width: 120, sorter: 'default' },
  {
    title: '时间',
    key: 'created_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.created_at),
  },
]

const loadData = async (params: LogSearchParams) => {
  const res = await getOperationLogs(params)
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
      title="审计日志"
      :columns="columns"
      :request="loadData"
      :row-key="(row: OperationLog) => row.id"
      search-placeholder="搜索用户名/IP/模块/摘要/路径"
      :scroll-x="1400"
    />
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}
</style>

