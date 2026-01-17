<script setup lang="ts">
import { ref } from 'vue'
import {
  NDrawer,
  NDrawerContent,
  NDescriptions,
  NDescriptionsItem,
  type DataTableColumns,
  type DropdownOption,
} from 'naive-ui'
import {
  getOperationLogs,
  exportOperationLogs,
  type LogSearchParams,
  type OperationLog,
} from '@/api/logs'
import { formatDateTime } from '@/utils/date'
import ProTable from '@/components/common/ProTable.vue'
import DataImportExport from '@/components/common/DataImportExport.vue'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import 'highlight.js/styles/github.css'

// 注册 JSON 语言
hljs.registerLanguage('json', json)

defineOptions({
  name: 'OperationLog',
})

const tableRef = ref()

const columns: DataTableColumns<OperationLog> = [
  { title: '用户名', key: 'username', width: 140, sorter: 'default' },
  { title: 'IP', key: 'ip', width: 140 },
  { title: '模块', key: 'module', width: 160, ellipsis: { tooltip: true } },
  { title: '摘要', key: 'summary', width: 220, ellipsis: { tooltip: true } },
  { title: '方法', key: 'method', width: 90 },
  { title: '路径', key: 'path', width: 220, ellipsis: { tooltip: true } },
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

// 右键菜单
const contextMenuOptions: DropdownOption[] = [{ label: '查看详情', key: 'detail' }]

// 抽屉状态
const showDrawer = ref(false)
const currentLog = ref<OperationLog | null>(null)

const handleContextMenuSelect = (key: string | number, row: OperationLog) => {
  if (key === 'detail') {
    currentLog.value = row
    showDrawer.value = true
  }
}

// 格式化并高亮 JSON
const highlightJson = (data: unknown): string => {
  if (!data) return '-'
  try {
    const jsonStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
    return hljs.highlight(jsonStr, { language: 'json' }).value
  } catch {
    return String(data)
  }
}

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
    <ProTable ref="tableRef" title="审计日志" :columns="columns" :request="loadData"
      :row-key="(row: OperationLog) => row.id" :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/IP/模块/摘要/路径" @context-menu-select="handleContextMenuSelect">
      <template #toolbar>
        <DataImportExport title="审计日志" show-export export-name="operation_logs_export.csv"
          :export-api="exportOperationLogs" />
      </template>
    </ProTable>

    <!-- 详情抽屉 -->
    <n-drawer v-model:show="showDrawer" :width="630" placement="right" :native-scrollbar="true">
      <n-drawer-content title="审计日志详情" closable>
        <n-descriptions v-if="currentLog" label-placement="left" :column="1" bordered>
          <n-descriptions-item label="ID">{{ currentLog.id }}</n-descriptions-item>
          <n-descriptions-item label="用户ID">{{ currentLog.user_id }}</n-descriptions-item>
          <n-descriptions-item label="用户名">{{ currentLog.username }}</n-descriptions-item>
          <n-descriptions-item label="IP">{{ currentLog.ip }}</n-descriptions-item>
          <n-descriptions-item label="模块">{{ currentLog.module || '-' }}</n-descriptions-item>
          <n-descriptions-item label="摘要">{{ currentLog.summary || '-' }}</n-descriptions-item>
          <n-descriptions-item label="方法">{{ currentLog.method }}</n-descriptions-item>
          <n-descriptions-item label="路径">{{ currentLog.path }}</n-descriptions-item>
          <n-descriptions-item label="状态码">{{ currentLog.response_code }}</n-descriptions-item>
          <n-descriptions-item label="耗时">{{ currentLog.duration?.toFixed(4) }} ms</n-descriptions-item>
          <n-descriptions-item label="User-Agent">{{
            currentLog.user_agent || '-'
            }}</n-descriptions-item>
          <n-descriptions-item label="时间">{{
            formatDateTime(currentLog.created_at)
            }}</n-descriptions-item>
        </n-descriptions>

        <div v-if="currentLog" class="json-section">
          <div class="json-title">请求参数 (params)</div>
          <pre class="json-code" v-html="highlightJson(currentLog.params)"></pre>

          <div class="json-title">响应结果 (response_result)</div>
          <pre class="json-code" v-html="highlightJson(currentLog.response_result)"></pre>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}

.json-section {
  margin-top: 16px;
}

.json-title {
  font-weight: 500;
  margin: 16px 0 8px;
  color: #333;
}

.json-code {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}
</style>
