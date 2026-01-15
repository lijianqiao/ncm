<script setup lang="ts">
import { ref, h, computed, onMounted } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  NSelect,
  NInputNumber,
  useDialog,
  type DataTableColumns,
  NTag,
  NSpace,
  NAlert,
  NTreeSelect,
  NTabs,
  NTabPane,
  NTable,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getDiscoveryRecords,
  triggerScan,
  getScanTaskStatus,
  deleteDiscoveryRecord,
  batchDeleteDiscoveryRecords,
  adoptDevice,
  getShadowAssets,
  getOfflineDevices,
  compareCMDB,
  getRecycleBinDiscoveryRecords,
  restoreDiscoveryRecord,
  batchRestoreDiscoveryRecords,
  hardDeleteDiscoveryRecord,
  batchHardDeleteDiscoveryRecords,
  type DiscoveryRecord,
  type DiscoverySearchParams,
  type DiscoveryStatus,
  type ScanTaskStatus,
  type OfflineDevice,
} from '@/api/discovery'
import { type DeviceGroup } from '@/api/devices'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'
import { usePersistentTaskPolling } from '@/composables'

defineOptions({
  name: 'DiscoveryManagement',
})

const dialog = useDialog()
const tableRef = ref()
const recycleBinRef = ref()
const showRecycleBin = ref(false)

// ==================== 常量定义 ====================

const statusOptions = [
  { label: '已匹配', value: 'matched' },
  { label: '待确认', value: 'pending' },
  { label: '影子资产', value: 'shadow' },
  { label: '离线设备', value: 'offline' },
]

const statusLabelMap: Record<DiscoveryStatus, string> = {
  matched: '已匹配',
  pending: '待确认',
  shadow: '影子资产',
  offline: '离线设备',
}

const statusColorMap: Record<DiscoveryStatus, 'info' | 'default' | 'success'> = {
  matched: 'success',
  pending: 'info',
  shadow: 'default',
  offline: 'default',
}

const deviceGroupOptions = [
  { label: '核心层', value: 'core' },
  { label: '汇聚层', value: 'distribution' },
  { label: '接入层', value: 'access' },
  { label: '防火墙', value: 'firewall' },
  { label: '无线', value: 'wireless' },
  { label: '其他', value: 'other' },
]

const scanTypeOptions = [
  { label: '自动', value: 'auto' },
  { label: 'Nmap', value: 'nmap' },
  { label: 'Masscan', value: 'masscan' },
]

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

onMounted(() => {
  fetchDeptTree()
})

const deptNameMap = computed<Record<string, string>>(() => {
  const map: Record<string, string> = {}
  const walk = (items: TreeSelectOption[], prefix = '') => {
    for (const it of items) {
      const label = prefix ? `${prefix} / ${it.label}` : it.label
      map[it.key] = label
      if (it.children && it.children.length) walk(it.children, label)
    }
  }
  walk(deptTreeOptions.value || [])
  return map
})

const getDeviceTypeFromSnmpSysdescr = (
  vendor: string | null | undefined,
  sysDescr: string | null | undefined,
) => {
  if (!sysDescr) return null
  const lines = sysDescr
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (lines.length === 0) return null

  const v = (vendor || '').toLowerCase()

  if (v === 'h3c') {
    if (lines.length >= 2) return lines[1]
    return lines[0]
  }
  if (v === 'huawei') {
    return lines[0]
  }
  if (v === 'cisco') {
    const hit = lines.find((l) => /cisco/i.test(l))
    return hit || lines[0]
  }

  const h3cLine = lines.find((l) => /^h3c\b/i.test(l))
  if (h3cLine) return h3cLine
  const huaweiModel = lines.find((l) => /^s\d{3,4}-/i.test(l))
  if (huaweiModel) return huaweiModel

  return lines[0]
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<DiscoveryRecord> = [
  { type: 'selection', fixed: 'left' },
  {
    title: 'IP 地址',
    key: 'ip_address',
    width: 140,
    fixed: 'left',
    sorter: 'default',
    resizable: true,
  },
  {
    title: 'MAC 地址',
    key: 'mac_address',
    width: 150,
    sorter: 'default',
    resizable: true,
    render: (row) => row.mac_address || '-',
  },
  {
    title: '厂商',
    key: 'vendor',
    width: 120,
    sorter: 'default',
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => row.vendor || '-',
  },
  {
    title: '主机名',
    key: 'hostname',
    width: 160,
    sorter: 'default',
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => row.hostname || row.snmp_sysname || '-',
  },
  {
    title: '所属部门',
    key: 'dept_id',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => {
      const id = row.dept_id
      if (!id) return '-'
      return deptNameMap.value[id] || id
    },
  },
  {
    title: '设备类型',
    key: 'device_type',
    width: 200,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) =>
      getDeviceTypeFromSnmpSysdescr(row.vendor, row.snmp_sysdescr) || row.device_type || '-',
  },
  {
    title: '序列号',
    key: 'serial_number',
    width: 180,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => row.serial_number || '-',
  },
  {
    title: 'SNMP',
    key: 'snmp_ok',
    width: 90,
    render: (row) => {
      if (row.snmp_ok === true)
        return h(
          NTag,
          { type: 'success', bordered: false, size: 'small' },
          { default: () => '成功' },
        )
      if (row.snmp_ok === false)
        return h(NTag, { type: 'error', bordered: false, size: 'small' }, { default: () => '失败' })
      return '-'
    },
  },
  {
    title: 'SNMP 错误',
    key: 'snmp_error',
    width: 240,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => (row.snmp_ok === false ? row.snmp_error || '-' : '-'),
  },
  {
    title: '开放端口',
    key: 'open_ports',
    width: 160,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => {
      const ports = row.open_ports
      if (!ports) return '-'
      const keys = Object.keys(ports)
      if (keys.length === 0) return '-'
      return keys
        .sort((a, b) => Number(a) - Number(b))
        .map((p) => `${p}/${ports[p] || '-'}`)
        .join(', ')
    },
  },
  {
    title: 'SSH Banner',
    key: 'ssh_banner',
    width: 220,
    sorter: 'default',
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => row.ssh_banner || '-',
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render(row) {
      return h(
        NTag,
        { type: statusColorMap[row.status], bordered: false, size: 'small' },
        { default: () => statusLabelMap[row.status] },
      )
    },
  },
  {
    title: '匹配设备',
    key: 'matched_device_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.matched_device_name || '-',
  },
  {
    title: '扫描方式',
    key: 'scan_source',
    width: 90,
    sorter: 'default',
    resizable: true,
    render: (row) => row.scan_source || '-',
  },
  {
    title: '首次扫描',
    key: 'first_seen_at',
    width: 160,
    sorter: 'default',
    resizable: true,
    render: (row) => formatDateTime(row.first_seen_at),
  },
  {
    title: '最后一次扫描',
    key: 'last_seen_at',
    width: 160,
    sorter: 'default',
    resizable: true,
    render: (row) => formatDateTime(row.last_seen_at),
  },
  { title: '离线天数', key: 'offline_days', width: 90, sorter: 'default', resizable: true },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: DiscoverySearchParams) => {
  const res = await getDiscoveryRecords(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const recycleBinRequest = async (params: DiscoverySearchParams) => {
  const res = await getRecycleBinDiscoveryRecords(params)
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
    content: `确定要删除选中的 ${ids.length} 条发现记录吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteDiscoveryRecords(ids.map(String))
        $alert.success(`成功删除 ${res.data.success_count} 条记录`)
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleRecycleBinRestore = async (row: DiscoveryRecord) => {
  try {
    await restoreDiscoveryRecord(row.id)
    $alert.success('恢复成功')
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinBatchRestore = async (ids: Array<string | number>) => {
  try {
    const res = await batchRestoreDiscoveryRecords(ids.map(String))
    $alert.success(`成功恢复 ${res.data.success_count} 条记录`)
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinHardDelete = async (row: DiscoveryRecord) => {
  try {
    await hardDeleteDiscoveryRecord(row.id)
    $alert.success('彻底删除成功')
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleRecycleBinBatchHardDelete = async (ids: Array<string | number>) => {
  try {
    const res = await batchHardDeleteDiscoveryRecords(ids.map(String))
    $alert.success(`成功彻底删除 ${res.data.success_count} 条记录`)
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看 SNMP 详情', key: 'snmp' },
  { label: '纳管设备', key: 'adopt' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: DiscoveryRecord) => {
  if (key === 'snmp') handleShowSnmp(row)
  if (key === 'adopt') handleAdopt(row)
  if (key === 'delete') handleDelete(row)
}

const handleShowSnmp = (row: DiscoveryRecord) => {
  const items: Array<{ label: string; value: string }> = [
    { label: 'IP', value: row.ip_address },
    { label: 'SNMP', value: row.snmp_ok === true ? '成功' : row.snmp_ok === false ? '失败' : '-' },
    { label: 'sysName', value: row.snmp_sysname || '-' },
    { label: 'sysDescr', value: row.snmp_sysdescr || '-' },
    { label: '错误', value: row.snmp_ok === false ? row.snmp_error || '-' : '-' },
  ]
  dialog.info({
    title: 'SNMP 详情',
    content: () =>
      h(
        'div',
        { style: { lineHeight: '22px' } },
        items.map((it) =>
          h('div', { key: it.label }, [
            h('span', { style: { color: 'var(--n-text-color-3)' } }, `${it.label}: `),
            it.value,
          ]),
        ),
      ),
    positiveText: '关闭',
  })
}

// ==================== 删除 ====================

const handleDelete = (row: DiscoveryRecord) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除发现记录 ${row.ip_address} 吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteDiscoveryRecord(row.id)
        $alert.success('记录已删除')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 纳管设备 ====================

const showAdoptModal = ref(false)
const adoptModel = ref({
  discovery_id: '',
  ip_address: '',
  name: '',
  vendor: '',
  device_group: '' as DeviceGroup | '',
  dept_id: '',
  username: '',
  password: '',
})

const handleAdopt = (row: DiscoveryRecord) => {
  if (row.status === 'matched') {
    $alert.warning('该设备已被纳管')
    return
  }
  adoptModel.value = {
    discovery_id: row.id,
    ip_address: row.ip_address,
    name: row.hostname || row.snmp_sysname || row.ip_address,
    vendor: row.vendor || '',
    device_group: '',
    dept_id: '',
    username: '',
    password: '',
  }
  fetchDeptTree()
  showAdoptModal.value = true
}

const submitAdopt = async () => {
  if (!adoptModel.value.name) {
    $alert.warning('请输入设备名称')
    return
  }
  try {
    await adoptDevice(adoptModel.value.discovery_id, {
      name: adoptModel.value.name,
      vendor: adoptModel.value.vendor || undefined,
      device_group: adoptModel.value.device_group || undefined,
      dept_id: adoptModel.value.dept_id || undefined,
      username: adoptModel.value.username || undefined,
      password: adoptModel.value.password || undefined,
    })
    $alert.success('设备已纳管')
    showAdoptModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 触发扫描 ====================

const showScanModal = ref(false)
const scanModel = ref({
  subnets: '',
  scan_type: 'auto' as 'auto' | 'nmap' | 'masscan',
  ports: '22,23,80,443',
  async_mode: true,
  dept_id: '',
})

const DISCOVERY_SCAN_TASK_ID_KEY = 'ncm.discovery.scan_task_id'

// 使用 usePersistentTaskPolling composable
const {
  taskStatus: scanTaskStatus,
  isPolling: scanIsPolling,
  start: startPollingScanStatus,
  clear: clearScanTask,
} = usePersistentTaskPolling<ScanTaskStatus>((taskId) => getScanTaskStatus(taskId), {
  storageKey: DISCOVERY_SCAN_TASK_ID_KEY,
  interval: 5000,
  maxAttempts: 240,
  onComplete: () => {
    clearScanTask()
    tableRef.value?.reload()
  },
  onError: () => {
    clearScanTask()
    tableRef.value?.reload()
  },
})

const scanButtonType = computed<'primary' | 'default' | 'success' | 'error'>(() => {
  const status = scanTaskStatus.value?.status
  if (!status) return 'primary'
  if (scanIsPolling.value) return 'default'
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILURE') return 'error'
  return 'default'
})

const scanButtonText = computed(() => {
  const status = scanTaskStatus.value?.status
  if (!status) return '触发扫描'
  if (scanIsPolling.value) {
    const p = scanTaskStatus.value?.progress
    return p !== null && p !== undefined ? `扫描中 ${p}%` : '扫描中'
  }
  if (status === 'SUCCESS') return '✅完成'
  if (status === 'FAILURE') return '失败'
  return String(status)
})

const showScanStatusDetail = () => {
  const s = scanTaskStatus.value
  if (!s) return
  dialog.info({
    title: '扫描任务状态',
    content: `任务ID: ${s.task_id}\n状态: ${s.status}${s.error ? `\n错误: ${s.error}` : ''}`,
    positiveText: '关闭',
  })
}

const handleTriggerScan = () => {
  scanModel.value = {
    subnets: '',
    scan_type: 'auto',
    ports: '22,23,80,443',
    async_mode: true,
    dept_id: '',
  }
  fetchDeptTree()
  // 只重置表单，不打断已有扫描轮询
  showScanModal.value = true
}

const submitScan = async () => {
  if (!scanModel.value.subnets) {
    $alert.warning('请输入扫描网段')
    return
  }
  const subnets = scanModel.value.subnets
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (subnets.length === 0) {
    $alert.warning('请输入有效的网段')
    return
  }
  try {
    const res = await triggerScan({
      subnets,
      scan_type: scanModel.value.scan_type,
      ports: scanModel.value.ports || undefined,
      async_mode: scanModel.value.async_mode,
      dept_id: scanModel.value.dept_id || undefined,
    })
    if (res.data.task_id) {
      $alert.success('扫描任务已提交')
      startPollingScanStatus(res.data.task_id)
      showScanModal.value = false
    } else {
      $alert.success(res.data.message || '扫描完成')
      tableRef.value?.reload()
      showScanModal.value = false
    }
  } catch {
    // Error handled
  }
}

const closeScanModal = () => {
  showScanModal.value = false
}

// ==================== 影子资产 & 离线设备 ====================

const showExtraModal = ref(false)
const activeTab = ref('shadow')
const shadowAssets = ref<DiscoveryRecord[]>([])
const offlineDevices = ref<OfflineDevice[]>([])
const extraLoading = ref(false)
const offlineDaysThreshold = ref(7)

const handleShowExtra = async () => {
  showExtraModal.value = true
  extraLoading.value = true
  try {
    const [shadowRes, offlineRes] = await Promise.all([
      getShadowAssets({ page_size: 100 }),
      getOfflineDevices(offlineDaysThreshold.value),
    ])
    shadowAssets.value = shadowRes.data.items || []
    offlineDevices.value = offlineRes.data || []
  } catch {
    // Error handled
  } finally {
    extraLoading.value = false
  }
}

const refreshOfflineDevices = async () => {
  extraLoading.value = true
  try {
    const res = await getOfflineDevices(offlineDaysThreshold.value)
    offlineDevices.value = res.data || []
  } catch {
    // Error handled
  } finally {
    extraLoading.value = false
  }
}

// ==================== CMDB 比对 ====================

const handleCompareCMDB = () => {
  dialog.info({
    title: 'CMDB 比对',
    content: '确定要执行 CMDB 比对吗？这将对比发现的资产与正式设备库。',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await compareCMDB(true)
        if (res.data.task_id) {
          $alert.success('CMDB 比对任务已提交')
        } else {
          $alert.success('CMDB 比对完成')
          tableRef.value?.reload()
        }
      } catch {
        // Error handled
      }
    },
  })
}
</script>

<template>
  <div class="discovery-management p-4">
    <ProTable
      ref="tableRef"
      title="资产发现记录"
      :columns="columns"
      :request="loadData"
      :row-key="(row: DiscoveryRecord) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索IP/MAC/主机名"
      :search-filters="searchFilters"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      @batch-delete="handleBatchDelete"
      show-recycle-bin
      show-batch-delete
      :scroll-x="2000"
    >
      <template #toolbar-left>
        <n-space>
          <n-button
            :type="scanButtonType as any"
            :loading="scanIsPolling"
            @click="scanTaskStatus ? showScanStatusDetail() : handleTriggerScan()"
          >
            {{ scanButtonText }}
          </n-button>
          <n-button type="info" @click="handleShowExtra">影子资产/离线设备</n-button>
          <n-button @click="handleCompareCMDB">CMDB 比对</n-button>
        </n-space>
      </template>
    </ProTable>

    <RecycleBinModal
      ref="recycleBinRef"
      v-model:show="showRecycleBin"
      title="回收站 (已删除发现记录)"
      :columns="columns"
      :request="recycleBinRequest"
      :row-key="(row: DiscoveryRecord) => row.id"
      search-placeholder="搜索已删除记录..."
      :scroll-x="2000"
      @restore="handleRecycleBinRestore"
      @batch-restore="handleRecycleBinBatchRestore"
      @hard-delete="handleRecycleBinHardDelete"
      @batch-hard-delete="handleRecycleBinBatchHardDelete"
    />

    <!-- 触发扫描 Modal -->
    <n-modal
      v-model:show="showScanModal"
      preset="card"
      title="触发网络扫描"
      style="width: 600px"
      @close="closeScanModal"
    >
      <n-space vertical style="width: 100%">
        <n-form-item label="扫描网段 (每行一个或逗号分隔)">
          <n-input
            v-model:value="scanModel.subnets"
            type="textarea"
            placeholder="例如: 192.168.1.0/24, 10.0.0.0/24"
            :rows="3"
          />
        </n-form-item>
        <n-form-item label="所属部门（用于 SNMP 凭据匹配）">
          <n-tree-select
            v-model:value="scanModel.dept_id"
            :options="deptTreeOptions"
            placeholder="可选"
            clearable
            key-field="key"
            label-field="label"
          />
        </n-form-item>
        <n-form-item label="扫描类型">
          <n-select v-model:value="scanModel.scan_type" :options="scanTypeOptions" />
        </n-form-item>
        <n-form-item label="扫描端口">
          <n-input v-model:value="scanModel.ports" placeholder="22,23,80,443" />
        </n-form-item>
      </n-space>
      <div style="margin-top: 20px; text-align: right">
        <n-space>
          <n-button @click="closeScanModal">取消</n-button>
          <n-button type="primary" @click="submitScan">开始扫描</n-button>
        </n-space>
      </div>
    </n-modal>

    <!-- 纳管设备 Modal -->
    <n-modal v-model:show="showAdoptModal" preset="dialog" title="纳管设备" style="width: 500px">
      <n-space vertical style="width: 100%">
        <n-form-item label="IP 地址">
          <n-input :value="adoptModel.ip_address" disabled />
        </n-form-item>
        <n-form-item label="设备名称">
          <n-input v-model:value="adoptModel.name" placeholder="请输入设备名称" />
        </n-form-item>
        <n-form-item label="厂商">
          <n-input v-model:value="adoptModel.vendor" placeholder="设备厂商" />
        </n-form-item>
        <n-form-item label="设备分组">
          <n-select
            v-model:value="adoptModel.device_group"
            :options="deviceGroupOptions"
            placeholder="请选择设备分组"
            clearable
          />
        </n-form-item>
        <n-form-item label="所属部门">
          <n-tree-select
            v-model:value="adoptModel.dept_id"
            :options="deptTreeOptions"
            placeholder="请选择部门"
            clearable
            key-field="key"
            label-field="label"
          />
        </n-form-item>
        <n-form-item label="SSH 用户名">
          <n-input v-model:value="adoptModel.username" placeholder="SSH 用户名（可选）" />
        </n-form-item>
        <n-form-item label="SSH 密码">
          <n-input
            v-model:value="adoptModel.password"
            type="password"
            show-password-on="click"
            placeholder="SSH 密码（可选）"
          />
        </n-form-item>
      </n-space>
      <template #action>
        <n-button @click="showAdoptModal = false">取消</n-button>
        <n-button type="primary" @click="submitAdopt">纳管</n-button>
      </template>
    </n-modal>

    <!-- 影子资产 & 离线设备 Modal -->
    <n-modal
      v-model:show="showExtraModal"
      preset="card"
      title="影子资产 & 离线设备"
      style="width: 900px"
    >
      <div class="extra-modal-body">
        <n-tabs v-model:value="activeTab">
          <n-tab-pane name="shadow" tab="影子资产">
            <div v-if="extraLoading" style="text-align: center; padding: 40px">加载中...</div>
            <template v-else>
              <n-alert type="info" style="margin-bottom: 16px">
                影子资产是在网络中发现但未在 CMDB 中注册的设备
              </n-alert>
              <n-table :bordered="false" :single-line="false">
                <thead>
                  <tr>
                    <th>IP 地址</th>
                    <th>MAC 地址</th>
                    <th>厂商</th>
                    <th>主机名</th>
                    <th>首次发现</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in shadowAssets" :key="item.id">
                    <td>{{ item.ip_address }}</td>
                    <td>{{ item.mac_address || '-' }}</td>
                    <td>{{ item.vendor || '-' }}</td>
                    <td>{{ item.hostname || '-' }}</td>
                    <td>{{ formatDateTime(item.first_seen_at) }}</td>
                  </tr>
                  <tr v-if="shadowAssets.length === 0">
                    <td colspan="5" style="text-align: center">暂无影子资产</td>
                  </tr>
                </tbody>
              </n-table>
            </template>
          </n-tab-pane>
          <n-tab-pane name="offline" tab="离线设备">
            <div v-if="extraLoading" style="text-align: center; padding: 40px">加载中...</div>
            <template v-else>
              <n-space style="margin-bottom: 16px">
                <span>离线天数阈值:</span>
                <n-input-number v-model:value="offlineDaysThreshold" :min="1" :max="365" />
                <n-button @click="refreshOfflineDevices">刷新</n-button>
              </n-space>
              <n-table :bordered="false" :single-line="false">
                <thead>
                  <tr>
                    <th>设备名称</th>
                    <th>IP 地址</th>
                    <th>最后发现时间</th>
                    <th>离线天数</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in offlineDevices" :key="item.device_id">
                    <td>{{ item.device_name }}</td>
                    <td>{{ item.ip_address }}</td>
                    <td>{{ formatDateTime(item.last_seen_at) }}</td>
                    <td>
                      <n-tag :type="item.offline_days > 30 ? 'error' : 'warning'" size="small">
                        {{ item.offline_days }} 天
                      </n-tag>
                    </td>
                  </tr>
                  <tr v-if="offlineDevices.length === 0">
                    <td colspan="4" style="text-align: center">暂无离线设备</td>
                  </tr>
                </tbody>
              </n-table>
            </template>
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.discovery-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}

.extra-modal-body {
  max-height: 70vh;
  overflow: auto;
}
</style>
