<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  type DataTableColumns,
  NTag,
  NSpace,
  NDescriptions,
  NDescriptionsItem,
  NTable,
  NTabs,
  NTabPane,
  NTreeSelect,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getInventoryAudits,
  createInventoryAudit,
  getInventoryAudit,
  exportInventoryAudit,
  type InventoryAudit,
  type InventoryAuditSearchParams,
  type InventoryAuditStatus,
  type InventoryAuditReport,
} from '@/api/inventory'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'InventoryManagement',
})

const tableRef = ref()

// ==================== 常量定义 ====================

const statusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const statusLabelMap: Record<InventoryAuditStatus, string> = {
  pending: '待执行',
  running: '执行中',
  success: '成功',
  failed: '失败',
}

const statusColorMap: Record<InventoryAuditStatus, 'default' | 'info' | 'success' | 'error'> = {
  pending: 'default',
  running: 'info',
  success: 'success',
  failed: 'error',
}

// ==================== 部门树 ====================

interface TreeSelectOption {
  label: string
  key: string
  children?: TreeSelectOption[]
}
const deptTreeOptions = ref<TreeSelectOption[]>([])

const fetchDeptTree = async () => {
  try {
    const res = await getDeptTree()
    const transform = (items: Dept[]): TreeSelectOption[] => {
      return items.map((item) => ({
        label: item.name,
        key: item.id,
        children: item.children && item.children.length ? transform(item.children) : undefined,
      }))
    }
    deptTreeOptions.value = transform(res.data || [])
  } catch {
    // Error handled
  }
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<InventoryAudit> = [
  { type: 'selection', fixed: 'left' },
  { title: '任务名称', key: 'name', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
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
    title: '扫描总数',
    key: 'total_scanned',
    width: 100,
    render: (row) => row.stats?.total_scanned ?? '-',
  },
  {
    title: '在线',
    key: 'online_count',
    width: 80,
    render: (row) => row.stats?.online_count ?? '-',
  },
  {
    title: '离线',
    key: 'offline_count',
    width: 80,
    render: (row) => row.stats?.offline_count ?? '-',
  },
  {
    title: '影子资产',
    key: 'shadow_count',
    width: 100,
    render: (row) => row.stats?.shadow_count ?? '-',
  },
  {
    title: '配置差异',
    key: 'config_diff_count',
    width: 100,
    render: (row) => row.stats?.config_diff_count ?? '-',
  },
  {
    title: '创建人',
    key: 'created_by_name',
    width: 100,
    render: (row) => row.created_by_name || '-',
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '完成时间',
    key: 'completed_at',
    width: 180,
    render: (row) => formatDateTime(row.completed_at),
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: InventoryAuditSearchParams) => {
  const res = await getInventoryAudits(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看详情', key: 'view' },
  { label: '导出报告', key: 'export' },
]

const handleContextMenuSelect = (key: string | number, row: InventoryAudit) => {
  if (key === 'view') handleView(row)
  if (key === 'export') handleExport(row)
}

// ==================== 查看详情 ====================

const showViewModal = ref(false)
const viewData = ref<InventoryAudit | null>(null)
const viewLoading = ref(false)

const handleView = async (row: InventoryAudit) => {
  viewLoading.value = true
  showViewModal.value = true
  try {
    const res = await getInventoryAudit(row.id)
    viewData.value = res.data
  } catch {
    showViewModal.value = false
  } finally {
    viewLoading.value = false
  }
}

// ==================== 导出报告 ====================

const showExportModal = ref(false)
const exportData = ref<InventoryAuditReport | null>(null)
const exportLoading = ref(false)

const handleExport = async (row: InventoryAudit) => {
  if (row.status !== 'success') {
    $alert.warning('只能导出已完成的盘点报告')
    return
  }
  exportLoading.value = true
  showExportModal.value = true
  try {
    const res = await exportInventoryAudit(row.id)
    exportData.value = res.data
  } catch {
    showExportModal.value = false
  } finally {
    exportLoading.value = false
  }
}

const downloadReport = () => {
  if (!exportData.value) return
  const dataStr = JSON.stringify(exportData.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `inventory_audit_${exportData.value.audit.id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

// ==================== 创建盘点任务 ====================

const showCreateModal = ref(false)
const createModel = ref({
  name: '',
  subnets: '',
  dept_ids: [] as string[],
})

const handleCreate = async () => {
  createModel.value = {
    name: '',
    subnets: '',
    dept_ids: [],
  }
  await fetchDeptTree()
  showCreateModal.value = true
}

const submitCreate = async () => {
  if (!createModel.value.name) {
    $alert.warning('请输入任务名称')
    return
  }
  const subnets = createModel.value.subnets
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (subnets.length === 0 && createModel.value.dept_ids.length === 0) {
    $alert.warning('请输入扫描网段或选择部门')
    return
  }
  try {
    await createInventoryAudit({
      name: createModel.value.name,
      scope: {
        subnets: subnets.length > 0 ? subnets : undefined,
        dept_ids: createModel.value.dept_ids.length > 0 ? createModel.value.dept_ids : undefined,
      },
    })
    $alert.success('盘点任务已创建')
    showCreateModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}
</script>

<template>
  <div class="inventory-management p-4">
    <ProTable
      ref="tableRef"
      title="资产盘点任务"
      :columns="columns"
      :request="loadData"
      :row-key="(row: InventoryAudit) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索任务名称"
      :search-filters="searchFilters"
      @add="handleCreate"
      @context-menu-select="handleContextMenuSelect"
      show-add
      :scroll-x="1400"
    />

    <!-- 查看详情 Modal -->
    <n-modal v-model:show="showViewModal" preset="card" title="盘点任务详情" style="width: 700px">
      <div v-if="viewLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="viewData">
        <n-descriptions :column="2" label-placement="left" bordered>
          <n-descriptions-item label="任务名称" :span="2">{{ viewData.name }}</n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="statusColorMap[viewData.status]" size="small">
              {{ statusLabelMap[viewData.status] }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="创建人">{{ viewData.created_by_name || '-' }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ formatDateTime(viewData.created_at) }}</n-descriptions-item>
          <n-descriptions-item label="完成时间">{{ formatDateTime(viewData.completed_at) }}</n-descriptions-item>
          <n-descriptions-item label="扫描范围" :span="2">
            <template v-if="viewData.scope.subnets?.length">
              网段: {{ viewData.scope.subnets.join(', ') }}
            </template>
            <template v-if="viewData.scope.dept_ids?.length">
              部门 ID: {{ viewData.scope.dept_ids.join(', ') }}
            </template>
          </n-descriptions-item>
        </n-descriptions>
        <template v-if="viewData.stats">
          <h4 style="margin-top: 16px">盘点统计</h4>
          <n-descriptions :column="3" label-placement="left" bordered>
            <n-descriptions-item label="扫描总数">{{ viewData.stats.total_scanned }}</n-descriptions-item>
            <n-descriptions-item label="在线设备">{{ viewData.stats.online_count }}</n-descriptions-item>
            <n-descriptions-item label="离线设备">{{ viewData.stats.offline_count }}</n-descriptions-item>
            <n-descriptions-item label="已匹配">{{ viewData.stats.matched_count }}</n-descriptions-item>
            <n-descriptions-item label="影子资产">{{ viewData.stats.shadow_count }}</n-descriptions-item>
            <n-descriptions-item label="配置差异">{{ viewData.stats.config_diff_count }}</n-descriptions-item>
          </n-descriptions>
        </template>
        <template v-if="viewData.error">
          <h4 style="margin-top: 16px; color: #d03050">错误信息</h4>
          <p>{{ viewData.error }}</p>
        </template>
      </template>
    </n-modal>

    <!-- 导出报告 Modal -->
    <n-modal
      v-model:show="showExportModal"
      preset="card"
      title="盘点报告"
      style="width: 900px; max-height: 80vh; overflow: auto"
    >
      <div v-if="exportLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="exportData">
        <n-space justify="end" style="margin-bottom: 16px">
          <n-button type="primary" @click="downloadReport">下载 JSON</n-button>
        </n-space>
        <n-tabs type="line">
          <n-tab-pane name="online" :tab="`在线设备 (${exportData.online_devices.length})`">
            <n-table :bordered="false" :single-line="false">
              <thead>
                <tr>
                  <th>设备名称</th>
                  <th>IP 地址</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in exportData.online_devices" :key="item.device_id">
                  <td>{{ item.device_name }}</td>
                  <td>{{ item.ip_address }}</td>
                </tr>
                <tr v-if="exportData.online_devices.length === 0">
                  <td colspan="2" style="text-align: center">暂无数据</td>
                </tr>
              </tbody>
            </n-table>
          </n-tab-pane>
          <n-tab-pane name="offline" :tab="`离线设备 (${exportData.offline_devices.length})`">
            <n-table :bordered="false" :single-line="false">
              <thead>
                <tr>
                  <th>设备名称</th>
                  <th>IP 地址</th>
                  <th>离线天数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in exportData.offline_devices" :key="item.device_id">
                  <td>{{ item.device_name }}</td>
                  <td>{{ item.ip_address }}</td>
                  <td>
                    <n-tag :type="item.offline_days > 30 ? 'error' : 'warning'" size="small">
                      {{ item.offline_days }} 天
                    </n-tag>
                  </td>
                </tr>
                <tr v-if="exportData.offline_devices.length === 0">
                  <td colspan="3" style="text-align: center">暂无数据</td>
                </tr>
              </tbody>
            </n-table>
          </n-tab-pane>
          <n-tab-pane name="shadow" :tab="`影子资产 (${exportData.shadow_assets.length})`">
            <n-table :bordered="false" :single-line="false">
              <thead>
                <tr>
                  <th>IP 地址</th>
                  <th>MAC 地址</th>
                  <th>厂商</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in exportData.shadow_assets" :key="index">
                  <td>{{ item.ip_address }}</td>
                  <td>{{ item.mac_address || '-' }}</td>
                  <td>{{ item.vendor || '-' }}</td>
                </tr>
                <tr v-if="exportData.shadow_assets.length === 0">
                  <td colspan="3" style="text-align: center">暂无数据</td>
                </tr>
              </tbody>
            </n-table>
          </n-tab-pane>
          <n-tab-pane name="config_diff" :tab="`配置差异 (${exportData.config_diff_devices.length})`">
            <n-table :bordered="false" :single-line="false">
              <thead>
                <tr>
                  <th>设备名称</th>
                  <th>最后备份时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in exportData.config_diff_devices" :key="item.device_id">
                  <td>{{ item.device_name }}</td>
                  <td>{{ formatDateTime(item.last_backup_at) }}</td>
                </tr>
                <tr v-if="exportData.config_diff_devices.length === 0">
                  <td colspan="2" style="text-align: center">暂无数据</td>
                </tr>
              </tbody>
            </n-table>
          </n-tab-pane>
        </n-tabs>
      </template>
    </n-modal>

    <!-- 创建盘点任务 Modal -->
    <n-modal v-model:show="showCreateModal" preset="dialog" title="创建盘点任务" style="width: 600px">
      <n-space vertical style="width: 100%">
        <n-form-item label="任务名称">
          <n-input v-model:value="createModel.name" placeholder="请输入任务名称" />
        </n-form-item>
        <n-form-item label="扫描网段 (每行一个或逗号分隔)">
          <n-input
            v-model:value="createModel.subnets"
            type="textarea"
            placeholder="例如: 192.168.1.0/24, 10.0.0.0/24"
            :rows="3"
          />
        </n-form-item>
        <n-form-item label="或选择部门">
          <n-tree-select
            v-model:value="createModel.dept_ids"
            :options="deptTreeOptions"
            placeholder="请选择部门"
            multiple
            cascade
            checkable
            key-field="key"
            label-field="label"
          />
        </n-form-item>
      </n-space>
      <template #action>
        <n-button @click="showCreateModal = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">创建</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.inventory-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
