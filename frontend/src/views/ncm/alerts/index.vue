<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NModal,
  useDialog,
  type DataTableColumns,
  NTag,
  NDescriptions,
  NDescriptionsItem,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getAlerts,
  getAlert,
  acknowledgeAlert,
  closeAlert,
  type Alert,
  type AlertSearchParams,
  type AlertType,
  type AlertSeverity,
  type AlertStatus,
} from '@/api/alerts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'AlertManagement',
})

const dialog = useDialog()
const tableRef = ref()

// ==================== 常量定义 ====================

const alertTypeOptions = [
  { label: '设备离线', value: 'device_offline' },
  { label: '配置变更', value: 'config_change' },
  { label: '影子资产', value: 'shadow_asset' },
]

const severityOptions = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
]

const statusOptions = [
  { label: '未处理', value: 'open' },
  { label: '已确认', value: 'ack' },
  { label: '已关闭', value: 'closed' },
]

const alertTypeLabelMap: Record<AlertType, string> = {
  device_offline: '设备离线',
  config_change: '配置变更',
  shadow_asset: '影子资产',
}

const severityLabelMap: Record<AlertSeverity, string> = {
  low: '低',
  medium: '中',
  high: '高',
}

const statusLabelMap: Record<AlertStatus, string> = {
  open: '未处理',
  ack: '已确认',
  closed: '已关闭',
}

const severityColorMap: Record<AlertSeverity, 'info' | 'warning' | 'error'> = {
  low: 'info',
  medium: 'warning',
  high: 'error',
}

const statusColorMap: Record<AlertStatus, 'error' | 'warning' | 'success'> = {
  open: 'error',
  ack: 'warning',
  closed: 'success',
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<Alert> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '告警标题',
    key: 'title',
    width: 200,
    fixed: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: '类型',
    key: 'alert_type',
    width: 100,
    render: (row) => alertTypeLabelMap[row.alert_type],
  },
  {
    title: '级别',
    key: 'severity',
    width: 80,
    render(row) {
      return h(
        NTag,
        { type: severityColorMap[row.severity], bordered: false, size: 'small' },
        { default: () => severityLabelMap[row.severity] },
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: statusColorMap[row.status], bordered: false, size: 'small' },
        { default: () => statusLabelMap[row.status] },
      )
    },
  },
  {
    title: '关联设备',
    key: 'related_device_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.related_device_name || '-',
  },
  {
    title: '确认人',
    key: 'acknowledged_by',
    width: 100,
    render: (row) => row.acknowledged_by || '-',
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'alert_type', placeholder: '告警类型', options: alertTypeOptions, width: 120 },
  { key: 'severity', placeholder: '告警级别', options: severityOptions, width: 100 },
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: AlertSearchParams) => {
  const res = await getAlerts(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看详情', key: 'view' },
  { label: '确认告警', key: 'ack' },
  { label: '关闭告警', key: 'close' },
]

const handleContextMenuSelect = (key: string | number, row: Alert) => {
  if (key === 'view') handleViewDetail(row)
  if (key === 'ack') handleAcknowledge(row)
  if (key === 'close') handleClose(row)
}

// ==================== 查看详情 ====================

const showDetailModal = ref(false)
const detailData = ref<Alert | null>(null)
const detailLoading = ref(false)

const handleViewDetail = async (row: Alert) => {
  detailLoading.value = true
  showDetailModal.value = true
  try {
    const res = await getAlert(row.id)
    detailData.value = res.data
  } catch {
    showDetailModal.value = false
  } finally {
    detailLoading.value = false
  }
}

// ==================== 确认告警 ====================

const handleAcknowledge = (row: Alert) => {
  if (row.status !== 'open') {
    $alert.warning('只能确认未处理的告警')
    return
  }
  dialog.info({
    title: '确认告警',
    content: `确定要确认告警 "${row.title}" 吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await acknowledgeAlert(row.id)
        $alert.success('告警已确认')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 关闭告警 ====================

const handleClose = (row: Alert) => {
  if (row.status === 'closed') {
    $alert.warning('该告警已关闭')
    return
  }
  dialog.warning({
    title: '关闭告警',
    content: `确定要关闭告警 "${row.title}" 吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await closeAlert(row.id)
        $alert.success('告警已关闭')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 批量操作 ====================

const handleBatchAcknowledge = () => {
  const selectedKeys = tableRef.value?.getSelectedKeys() || []
  if (selectedKeys.length === 0) {
    $alert.warning('请先选择告警')
    return
  }
  dialog.info({
    title: '批量确认',
    content: `确定要确认选中的 ${selectedKeys.length} 条告警吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        for (const id of selectedKeys) {
          await acknowledgeAlert(id as string)
        }
        $alert.success('批量确认成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchClose = () => {
  const selectedKeys = tableRef.value?.getSelectedKeys() || []
  if (selectedKeys.length === 0) {
    $alert.warning('请先选择告警')
    return
  }
  dialog.warning({
    title: '批量关闭',
    content: `确定要关闭选中的 ${selectedKeys.length} 条告警吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        for (const id of selectedKeys) {
          await closeAlert(id as string)
        }
        $alert.success('批量关闭成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}
</script>

<template>
  <div class="alert-management p-4">
    <ProTable
      ref="tableRef"
      title="告警列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Alert) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索告警标题/内容"
      :search-filters="searchFilters"
      @context-menu-select="handleContextMenuSelect"
      :scroll-x="1200"
    >
      <template #toolbar-left>
        <n-button type="info" @click="handleBatchAcknowledge">批量确认</n-button>
        <n-button type="warning" @click="handleBatchClose">批量关闭</n-button>
      </template>
    </ProTable>

    <!-- 告警详情 Modal -->
    <n-modal
      v-model:show="showDetailModal"
      preset="card"
      title="告警详情"
      style="width: 700px"
    >
      <div v-if="detailLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="detailData">
        <n-descriptions :column="2" label-placement="left" bordered>
          <n-descriptions-item label="告警标题" :span="2">
            {{ detailData.title }}
          </n-descriptions-item>
          <n-descriptions-item label="告警类型">
            {{ alertTypeLabelMap[detailData.alert_type] }}
          </n-descriptions-item>
          <n-descriptions-item label="告警级别">
            <n-tag :type="severityColorMap[detailData.severity]" size="small">
              {{ severityLabelMap[detailData.severity] }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="statusColorMap[detailData.status]" size="small">
              {{ statusLabelMap[detailData.status] }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="关联设备">
            {{ detailData.related_device_name || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="告警内容" :span="2">
            {{ detailData.content || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="创建时间">
            {{ formatDateTime(detailData.created_at) }}
          </n-descriptions-item>
          <n-descriptions-item label="更新时间">
            {{ formatDateTime(detailData.updated_at) }}
          </n-descriptions-item>
          <n-descriptions-item label="确认人">
            {{ detailData.acknowledged_by || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="确认时间">
            {{ formatDateTime(detailData.acknowledged_at) }}
          </n-descriptions-item>
          <n-descriptions-item label="关闭人">
            {{ detailData.closed_by || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="关闭时间">
            {{ formatDateTime(detailData.closed_at) }}
          </n-descriptions-item>
        </n-descriptions>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.alert-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
