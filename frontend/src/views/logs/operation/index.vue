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
import {
  renderIpAddress,
  renderModule,
  renderHttpMethod,
  renderStatusCode,
  renderDuration,
  renderPath,
  renderUuid,
} from '@/composables/useStyledRenders'
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
  {
    title: 'IP',
    key: 'ip',
    width: 160,
    render: (row) => renderIpAddress(row.ip),
  },
  {
    title: '模块',
    key: 'module',
    width: 140,
    render: (row) => renderModule(row.module),
  },
  { title: '摘要', key: 'summary', width: 200, ellipsis: { tooltip: true } },
  {
    title: '方法',
    key: 'method',
    width: 90,
    render: (row) => renderHttpMethod(row.method),
  },
  {
    title: '路径',
    key: 'path',
    width: 200,
    render: (row) => renderPath(row.path, 180),
  },
  {
    title: '状态码',
    key: 'response_code',
    width: 90,
    sorter: 'default',
    render: (row) => renderStatusCode(row.response_code),
  },
  {
    title: '耗时',
    key: 'duration',
    width: 110,
    sorter: 'default',
    render: (row) => renderDuration(row.duration),
  },
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
    <n-drawer v-model:show="showDrawer" :width="680" placement="right" :native-scrollbar="true">
      <n-drawer-content title="审计日志详情" closable>
        <n-descriptions v-if="currentLog" label-placement="left" :column="1" bordered>
          <n-descriptions-item label="ID">
            <component :is="renderUuid(currentLog.id)" />
          </n-descriptions-item>
          <n-descriptions-item label="用户ID">
            <component :is="renderUuid(currentLog.user_id)" />
          </n-descriptions-item>
          <n-descriptions-item label="用户名">
            <span class="font-medium">{{ currentLog.username }}</span>
          </n-descriptions-item>
          <n-descriptions-item label="IP地址">
            <component :is="renderIpAddress(currentLog.ip)" />
          </n-descriptions-item>
          <n-descriptions-item label="模块">
            <component :is="renderModule(currentLog.module)" />
          </n-descriptions-item>
          <n-descriptions-item label="摘要">{{ currentLog.summary || '-' }}</n-descriptions-item>
          <n-descriptions-item label="方法">
            <component :is="renderHttpMethod(currentLog.method)" />
          </n-descriptions-item>
          <n-descriptions-item label="路径">
            <code class="path-code">{{ currentLog.path }}</code>
          </n-descriptions-item>
          <n-descriptions-item label="状态码">
            <component :is="renderStatusCode(currentLog.response_code)" />
          </n-descriptions-item>
          <n-descriptions-item label="耗时">
            <component :is="renderDuration(currentLog.duration)" />
          </n-descriptions-item>
          <n-descriptions-item label="User-Agent">{{ currentLog.user_agent || '-' }}</n-descriptions-item>
          <n-descriptions-item label="时间">{{ formatDateTime(currentLog.created_at) }}</n-descriptions-item>
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

.font-medium {
  font-weight: 500;
}

.path-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: #476582;
  word-break: break-all;
}

.json-section {
  margin-top: 16px;
}

.json-title {
  font-weight: 500;
  margin: 16px 0 8px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.json-title::before {
  content: '';
  width: 3px;
  height: 14px;
  background: #18a058;
  border-radius: 2px;
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
