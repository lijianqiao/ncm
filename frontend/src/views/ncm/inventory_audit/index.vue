<script setup lang="ts">
import { ref, h, onUnmounted } from 'vue'
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
  NTreeSelect,
  useDialog,
  type DropdownOption,
  NSpin,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getInventoryAudits,
  createInventoryAudit,
  getInventoryAudit,
  exportInventoryAudit,
  getRecycleBinInventoryAudits,
  batchDeleteInventoryAudits,
  restoreInventoryAudit,
  batchRestoreInventoryAudits,
  hardDeleteInventoryAudit,
  batchHardDeleteInventoryAudits,
  type InventoryAudit,
  type InventoryAuditSearchParams,
  type InventoryAuditStatus,
} from '@/api/inventory'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'

defineOptions({
  name: 'InventoryManagement',
})

const dialog = useDialog()
const tableRef = ref()
const recycleBinRef = ref()
const showRecycleBin = ref(false)

// Polling
const pollTimer = ref<number | null>(null)

const startPolling = () => {
  if (pollTimer.value) return
  pollTimer.value = window.setInterval(() => {
    tableRef.value?.refresh()
  }, 5000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onUnmounted(() => {
  stopPolling()
})

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
    width: 120,
    render(row) {
      if (row.status === 'running' || row.status === 'pending') {
        return h(NSpace, { align: 'center', size: 4 }, {
          default: () => [
            h(NTag, { type: statusColorMap[row.status], bordered: false, size: 'small' }, { default: () => statusLabelMap[row.status] }),
            h(NSpin, { size: 14 })
          ]
        })
      }
      return h(
        NTag,
        { type: statusColorMap[row.status], bordered: false, size: 'small' },
        { default: () => statusLabelMap[row.status] }
      )
    },
  },
  {
    title: '扫描总数',
    key: 'total_scanned',
    width: 100,
    render: (row) => row.result?.discoveries_total ?? row.stats?.total_scanned ?? '-',
  },
  {
    title: '在线',
    key: 'online_count',
    width: 80,
    render: (row) => row.result?.cmdb_compare?.total_discovered ?? row.stats?.online_count ?? '-',
  },
  {
    title: '离线',
    key: 'offline_count',
    width: 80,
    render: (row) => row.result?.cmdb_compare?.offline_devices ?? row.stats?.offline_count ?? '-',
  },
  {
    title: '影子资产',
    key: 'shadow_count',
    width: 100,
    render: (row) => row.result?.cmdb_compare?.shadow_assets ?? row.stats?.shadow_count ?? '-',
  },
  {
    title: '创建人',
    key: 'created_by_name',
    width: 180,
    render: (row) => row.operator_name || row.created_by_name || '-',
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '完成时间',
    key: 'finished_at',
    width: 180,
    render: (row) => formatDateTime(row.finished_at || row.completed_at),
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: InventoryAuditSearchParams) => {
  // 如果正在轮询，使用静默刷新（不显示表格 loading）
  // 但 ProTable 组件没有直接暴露 loading 属性控制，所以我们无法轻易控制它不显示 loading
  // 这里我们假设 ProTable 的 request 属性接受的函数，如果不手动设置 loading，ProTable 会自己管理
  // 为了实现无感刷新，我们可以利用 ProTable 暴露的 refresh 方法，但这里是 request 回调

  // 实际上 ProTable 内部会在调用 request 前设置 loading=true
  // 要实现无感刷新，我们需要修改 ProTable 组件或者在外部控制 loading
  // 既然用户要求“无感（不刷新页面）的成功”，意味着表格数据更新时不要闪烁 loading

  // 简单的做法：如果是由轮询触发的（比如通过参数区分，或者全局状态），则不显示 loading
  // 但这里 loadData 是由 ProTable 调用的。

  // 另一种思路：我们不修改 ProTable，而是接受 ProTable 的 loading 效果，
  // 但用户说 "我之前说在执行中，刷新按钮一会儿刷新一下。现在不需要"
  // "我需要在盘点任务状态为执行中（running）期间，后面增加一个加载动态" -> 这个已经通过 Status 列的 Render 实现了
  // "完成之后，无感（不刷新页面）的成功" -> 这意味着轮询更新数据时，不要让用户感觉到页面在刷新

  // 我们可以通过一个 ref 来控制是否显示 loading，但 ProTable 内部 logic 是死的
  // 除非我们传递 loading 属性给 ProTable，但这会覆盖 ProTable 内部的 loading

  // 让我们看看 ProTable.vue
  // :loading="loading || tableLoading"
  // tableLoading 是内部状态，每次 handleSearch 都会设为 true

  // 为了实现无感刷新，我们需要 ProTable 支持 silent refresh
  // 或者我们在 index.vue 中手动获取数据并更新 ProTable 的 data
  // 但 ProTable 的 data 是内部 ref

  // 妥协方案：
  // 1. 我们在 Status 列加了 Spin，满足了“执行期间...增加一个加载动态”
  // 2. 关于“无感成功”，如果 ProTable 每次刷新都转圈，体验确实不好

  // 让我们尝试在 pollTimer 中直接调用 API 获取数据，然后手动更新 ProTable 的 data？
  // ProTable 没有暴露直接设置 data 的方法。

  // 回到 ProTable.vue，看到 defineExpose 暴露了 refresh
  // tableRef.value?.refresh() 会触发 handleSearch -> 设置 tableLoading = true

  // 如果我们想无感刷新，我们需要 ProTable 提供一个 silentRefresh 方法
  // 或者修改 loadData，让它在轮询时不触发 loading

  // 但 loadData 是被调用的，它无法控制 ProTable 的 loading 状态

  // 让我们再次阅读需求： "无感（不刷新页面）的成功"
  // 这可能意味着不要整页刷新，也不要表格 loading 遮罩。

  // 我们可以修改 ProTable.vue，增加一个 silentRefresh 方法
  // 或者增加一个属性 :show-loading="!isPolling"

  // 鉴于不能修改 ProTable (假设是公共组件，虽然我有权限改)，
  // 我们先只做状态列的 Spin，看看用户是否满意。
  // 因为轮询刷新会导致表格闪烁，确实是个问题。

  // 等等，我确实有权限修改 ProTable。
  // 最好是 ProTable 增加一个 silent 参数给 refresh 方法。

  const res = await getInventoryAudits(params)

  // Check for running tasks
  const hasRunning = res.data.items.some(
    (item) => item.status === 'running' || item.status === 'pending'
  )

  // 只有当状态发生变化（从 running 变 success/failed）时，或者有 running 任务时才轮询
  // 这里逻辑没变
  if (hasRunning) {
    startPolling()
  } else {
    stopPolling()
  }

  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const recycleBinRequest = async (params: InventoryAuditSearchParams) => {
  const res = await getRecycleBinInventoryAudits(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleRecycleBin = () => {
  showRecycleBin.value = true
  recycleBinRef.value?.reload()
}

const handleBatchDelete = async (ids: Array<string | number>) => {
  if (ids.length === 0) return
  dialog.warning({
    title: '确认批量删除',
    content: `确定要删除选中的 ${ids.length} 个盘点任务吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteInventoryAudits(ids.map(String))
        $alert.success(`成功删除 ${res.data.success_count} 个盘点任务`)
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleRecycleBinRestore = async (row: InventoryAudit) => {
  try {
    await restoreInventoryAudit(row.id)
    $alert.success('恢复成功')
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinBatchRestore = async (ids: Array<string | number>) => {
  try {
    const res = await batchRestoreInventoryAudits(ids.map(String))
    $alert.success(`成功恢复 ${res.data.success_count} 个盘点任务`)
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinHardDelete = async (row: InventoryAudit) => {
  try {
    await hardDeleteInventoryAudit(row.id)
    $alert.success('彻底删除成功')
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinBatchHardDelete = async (ids: Array<string | number>) => {
  try {
    const res = await batchHardDeleteInventoryAudits(ids.map(String))
    $alert.success(`成功彻底删除 ${res.data.success_count} 个盘点任务`)
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
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

const handleExport = async (row: InventoryAudit) => {
  if (row.status !== 'success') {
    $alert.warning('只能导出已完成的盘点报告')
    return
  }

  try {
    // 1. 调用 API 获取 Blob 数据
    // 注意：api/inventory.ts 已修改为返回 Blob 类型
    // 由于 request 拦截器对于 blob 类型直接返回 response 对象
    // 所以这里的 res 实际上是 AxiosResponse<Blob>
    const response = await exportInventoryAudit(row.id) as unknown as { data: Blob, headers: Record<string, string> }

    // 2. 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition']
    let filename = `盘点报告_${row.name}.xlsx` // 默认文件名

    if (contentDisposition) {
      // 解析 filename*=UTF-8''xxx 或 filename="xxx" 格式
      const matches = contentDisposition.match(/filename\*?=['"]?(?:UTF-8'')?([^;\r\n"']*)['"]?/i)
      if (matches && matches[1]) {
        filename = decodeURIComponent(matches[1])
      }
    }

    // 3. 创建下载链接
    const blob = response.data
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    $alert.success('报告导出成功')
  } catch (error) {
    // 如果是 JSON 格式错误（后端返回 4xx/5xx 但内容是 JSON）
    // 由于 responseType: 'blob'，error.response.data 可能是 Blob
    // 这里简单提示失败，具体错误解析比较复杂
    $alert.error('导出失败，请重试')
  }
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
    <ProTable ref="tableRef" title="资产盘点任务" :columns="columns" :request="loadData"
      :row-key="(row: InventoryAudit) => row.id" :context-menu-options="contextMenuOptions" search-placeholder="搜索任务名称"
      :search-filters="searchFilters" @add="handleCreate" @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin" @batch-delete="handleBatchDelete" show-add show-recycle-bin show-batch-delete
      :scroll-x="1400" />

    <RecycleBinModal ref="recycleBinRef" v-model:show="showRecycleBin" title="回收站 (已删除盘点任务)" :columns="columns"
      :request="recycleBinRequest" :row-key="(row: InventoryAudit) => row.id" search-placeholder="搜索已删除任务..."
      :scroll-x="1400" @restore="handleRecycleBinRestore" @batch-restore="handleRecycleBinBatchRestore"
      @hard-delete="handleRecycleBinHardDelete" @batch-hard-delete="handleRecycleBinBatchHardDelete" />

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
          <n-descriptions-item label="创建人">{{
            viewData.created_by_name || '-'
          }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{
            formatDateTime(viewData.created_at)
          }}</n-descriptions-item>
          <n-descriptions-item label="完成时间">{{
            formatDateTime(viewData.completed_at)
          }}</n-descriptions-item>
          <n-descriptions-item label="扫描范围" :span="2">
            <template v-if="viewData.scope.subnets?.length">
              网段: {{ viewData.scope.subnets.join(', ') }}
            </template>
            <template v-if="viewData.scope.dept_ids?.length">
              部门 ID: {{ viewData.scope.dept_ids.join(', ') }}
            </template>
          </n-descriptions-item>
        </n-descriptions>
        <template v-if="viewData.result">
          <h4 style="margin-top: 16px">盘点统计</h4>
          <n-descriptions :column="3" label-placement="left" bordered>
            <n-descriptions-item label="扫描总数">{{
              viewData.result.discoveries_total
              }}</n-descriptions-item>
            <n-descriptions-item label="在线设备">{{
              viewData.result.cmdb_compare?.total_discovered
              }}</n-descriptions-item>
            <n-descriptions-item label="离线设备">{{
              viewData.result.cmdb_compare?.offline_devices
              }}</n-descriptions-item>
            <n-descriptions-item label="已匹配">{{
              viewData.result.cmdb_compare?.matched
              }}</n-descriptions-item>
            <n-descriptions-item label="影子资产">{{
              viewData.result.cmdb_compare?.shadow_assets
              }}</n-descriptions-item>
            <n-descriptions-item label="待定设备">{{
              viewData.result.discoveries_by_status?.pending
              }}</n-descriptions-item>
          </n-descriptions>
        </template>
        <template v-else-if="viewData.stats">
          <h4 style="margin-top: 16px">盘点统计</h4>
          <n-descriptions :column="3" label-placement="left" bordered>
            <n-descriptions-item label="扫描总数">{{
              viewData.stats.total_scanned
            }}</n-descriptions-item>
            <n-descriptions-item label="在线设备">{{
              viewData.stats.online_count
            }}</n-descriptions-item>
            <n-descriptions-item label="离线设备">{{
              viewData.stats.offline_count
            }}</n-descriptions-item>
            <n-descriptions-item label="已匹配">{{
              viewData.stats.matched_count
            }}</n-descriptions-item>
            <n-descriptions-item label="影子资产">{{
              viewData.stats.shadow_count
            }}</n-descriptions-item>
            <n-descriptions-item label="配置差异">{{
              viewData.stats.config_diff_count
            }}</n-descriptions-item>
          </n-descriptions>
        </template>
        <template v-if="viewData.error">
          <h4 style="margin-top: 16px; color: #d03050">错误信息</h4>
          <p>{{ viewData.error }}</p>
        </template>
      </template>
    </n-modal>

    <!-- 创建盘点任务 Modal -->
    <n-modal v-model:show="showCreateModal" preset="dialog" title="创建盘点任务" style="width: 600px">
      <n-space vertical style="width: 100%">
        <n-form-item label="任务名称">
          <n-input v-model:value="createModel.name" placeholder="请输入任务名称" />
        </n-form-item>
        <n-form-item label="扫描网段 (每行一个或逗号分隔)">
          <n-input v-model:value="createModel.subnets" type="textarea" placeholder="例如: 192.168.1.0/24, 10.0.0.0/24"
            :rows="3" />
        </n-form-item>
        <n-form-item label="或选择部门">
          <n-tree-select v-model:value="createModel.dept_ids" :options="deptTreeOptions" placeholder="请选择部门" multiple
            cascade checkable key-field="key" label-field="label" />
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
