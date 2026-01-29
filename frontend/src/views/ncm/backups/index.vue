<script setup lang="ts">
import { ref, h, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  NButton,
  NModal,
  useDialog,
  type DataTableColumns,
  NTag,
  NAlert,
  NSelect,
  NSpace,
  NProgress,
  NSwitch,
  type DropdownOption,
} from 'naive-ui'
import hljs from 'highlight.js/lib/core'
import plaintext from 'highlight.js/lib/languages/plaintext'
import { $alert } from '@/utils/alert'
import {
  getBackups,
  getBackupContent,
  deleteBackup,
  batchDeleteBackups,
  backupDevice,
  batchBackup,
  getBackupTaskStatus,
  getRecycleBackups,
  restoreBackup,
  batchRestoreBackups,
  hardDeleteBackup,
  batchHardDeleteBackups,
  exportBackups,
  type Backup,
  type BackupSearchParams,
  type BackupTaskStatus,
} from '@/api/backups'
import { getDeviceOptions, type Device } from '@/api/devices'
import { getDeviceLatestDiff, type DiffResponse } from '@/api/diff'
import { cacheOTP, type OTPCacheRequest } from '@/api/credentials'
import { resumeTaskGroup } from '@/api/tasks'
import { formatDateTime } from '@/utils/date'
import { useTaskPolling, renderIpAddress, renderEnumTag } from '@/composables'
import {
  DeviceVendorLabels,
  DeviceVendorColors,
  DeviceGroupLabels,
  DeviceGroupColors,
  AuthTypeLabels,
  AuthTypeColors,
  BackupStatusLabels,
  BackupStatusColors,
} from '@/types/enum-labels'
import type { DeviceVendor, DeviceGroup, AuthType, BackupStatus, BackupTypeType } from '@/types/enums'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import UnifiedDiffViewer from '@/components/common/UnifiedDiffViewer.vue'
import OtpModal from '@/components/common/OtpModal.vue'
import DataImportExport from '@/components/common/DataImportExport.vue'
import DeviceSelector from '@/components/common/DeviceSelector.vue'

defineOptions({
  name: 'BackupManagement',
})

hljs.registerLanguage('plaintext', plaintext)

const dialog = useDialog()
const tableRef = ref()
const recycleBinTableRef = ref()
const autoRefresh = ref(false)
let autoRefreshTimer: number | null = null

const checkedRowKeys = ref<Array<string | number>>([])
const checkedRecycleBinRowKeys = ref<Array<string | number>>([])
const showRecycleBin = ref(false)

// ==================== 常量定义 ====================

const backupTypeOptions = [
  { label: '定时备份', value: 'scheduled' },
  { label: '手动备份', value: 'manual' },
  { label: '变更前备份', value: 'pre_change' },
  { label: '变更后备份', value: 'post_change' },
  { label: '增量备份', value: 'incremental' },
]

const deviceGroupOptions = [
  { label: '核心层', value: 'core' },
  { label: '汇聚层', value: 'distribution' },
  { label: '接入层', value: 'access' },
]

const authTypeOptions = [
  { label: '静态密码', value: 'static' },
  { label: 'OTP 种子', value: 'otp_seed' },
  { label: 'OTP 手动', value: 'otp_manual' },
]

const deviceStatusOptions = [
  { label: '在库', value: 'in_stock' },
  { label: '使用中', value: 'in_use' },
  { label: '活跃', value: 'active' },
  { label: '离线', value: 'offline' },
  { label: '已报废', value: 'retired' },
]

const vendorOptions = [
  { label: 'H3C', value: 'h3c' },
  { label: 'Huawei', value: 'huawei' },
  { label: 'Cisco', value: 'cisco' },
]

// 字符串键映射（用于模板直接访问）
const backupTypeLabelMap: Record<string, string> = {
  scheduled: '定时备份',
  manual: '手动备份',
  pre_change: '变更前备份',
  post_change: '变更后备份',
  incremental: '增量备份',
}

const backupTypeColorMap: Record<string, 'info' | 'success' | 'warning' | 'default'> = {
  scheduled: 'info',
  manual: 'default',
  pre_change: 'warning',
  post_change: 'success',
  incremental: 'info',
}

const deviceGroupLabels: Record<string, string> = {
  core: '核心层',
  distribution: '汇聚层',
  access: '接入层',
}

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<Backup> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '设备名称',
    key: 'device',
    width: 280,
    fixed: 'left',
    ellipsis: { tooltip: true },
    render: (row) => row.device?.name || row.device_name || row.device_id,
  },
  {
    title: '操作者',
    key: 'operator_id',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.operator_id || '-',
  },
  {
    title: 'IP',
    key: 'ip_address',
    width: 165,
    render: (row) => renderIpAddress(row.device?.ip_address),
  },
  {
    title: '部门',
    key: 'dept',
    width: 110,
    ellipsis: { tooltip: true },
    render: (row) => row.device?.dept?.name || '-',
  },
  {
    title: '厂商',
    key: 'vendor',
    width: 100,
    render: (row) =>
      row.device?.vendor
        ? renderEnumTag(row.device.vendor as DeviceVendor, DeviceVendorLabels, DeviceVendorColors)
        : '-',
  },
  {
    title: '型号',
    key: 'model',
    width: 130,
    ellipsis: { tooltip: true },
    render: (row) => row.device?.model || '-',
  },
  {
    title: '分组',
    key: 'device_group',
    width: 90,
    render: (row) =>
      row.device?.device_group
        ? renderEnumTag(
            row.device.device_group as DeviceGroup,
            DeviceGroupLabels,
            DeviceGroupColors,
          )
        : '-',
  },
  {
    title: '认证',
    key: 'auth_type',
    width: 100,
    render: (row) =>
      row.device?.auth_type
        ? renderEnumTag(row.device.auth_type as AuthType, AuthTypeLabels, AuthTypeColors)
        : '-',
  },
  {
    title: '备份类型',
    key: 'backup_type',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { type: backupTypeColorMap[row.backup_type] || 'default', bordered: false, size: 'small' },
        { default: () => backupTypeLabelMap[row.backup_type] || row.backup_type },
      ),
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) =>
      row.status
        ? renderEnumTag(row.status as BackupStatus, BackupStatusLabels, BackupStatusColors)
        : '-',
  },
  {
    title: '配置 Hash',
    key: 'md5_hash',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => {
      const hash = row.md5_hash || row.config_hash || ''
      return hash ? hash.substring(0, 12) + '...' : '-'
    },
  },
  {
    title: '文件大小',
    key: 'content_size',
    width: 100,
    render: (row) => formatFileSize(row.content_size || row.file_size || 0),
  },
  {
    title: '有内容',
    key: 'has_content',
    width: 80,
    render: (row) => {
      const ok = Boolean(row.has_content)
      return h(
        NTag,
        { type: ok ? 'success' : 'warning', bordered: false, size: 'small' },
        { default: () => (ok ? '是' : '否') },
      )
    },
  },
  {
    title: '备份时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '错误信息',
    key: 'error_message',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.error_message || '-',
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'backup_type', placeholder: '备份类型', options: backupTypeOptions, width: 120 },
  { key: 'device_group', placeholder: '设备分组', options: deviceGroupOptions, width: 120 },
  { key: 'auth_type', placeholder: '认证方式', options: authTypeOptions, width: 120 },
  { key: 'device_status', placeholder: '设备状态', options: deviceStatusOptions, width: 120 },
  { key: 'vendor', placeholder: '厂商', options: vendorOptions, width: 120 },
]

// ==================== 数据加载 ====================

const loadData = async (params: BackupSearchParams) => {
  const res = await getBackups(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleRefresh = () => {
  tableRef.value?.reload()
}

const setupAutoRefresh = () => {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
  if (!autoRefresh.value) return
  autoRefreshTimer = window.setInterval(() => {
    tableRef.value?.reload()
  }, 30000)
}

const recycleBinRequest = async (params: BackupSearchParams) => {
  const res = await getRecycleBackups(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看配置', key: 'view' },
  { label: '配置差异', key: 'diff' },
  { label: '删除', key: 'delete' },
]

const recycleBinContextMenuOptions: DropdownOption[] = [
  { label: '恢复', key: 'restore' },
  { label: '彻底删除', key: 'hard_delete' },
]

const handleContextMenuSelect = (key: string | number, row: Backup) => {
  if (key === 'view') handleViewContent(row)
  if (key === 'diff') handleViewDiff(row)
  if (key === 'delete') handleDelete(row)
}

const handleRecycleBinContextMenuSelect = (key: string | number, row: Backup) => {
  if (key === 'restore') handleRestore(row)
  if (key === 'hard_delete') handleHardDelete(row)
}

// ==================== 查看配置内容 ====================

const showContentModal = ref(false)
const contentData = ref({
  device_name: '',
  backup_type: 'scheduled' as BackupTypeType,
  content: '',
  md5_hash: '',
  created_at: '',
})
const contentLoading = ref(false)

const handleViewContent = async (row: Backup) => {
  contentLoading.value = true
  showContentModal.value = true
  try {
    contentData.value = {
      device_name: row.device?.name || row.device_name || row.device_id,
      backup_type: row.backup_type,
      content: '',
      md5_hash: row.md5_hash || row.config_hash || '',
      created_at: row.created_at,
    }
    const res = await getBackupContent(row.id)
    contentData.value = {
      ...contentData.value,
      content: res.data.content,
    }
  } catch {
    showContentModal.value = false
  } finally {
    contentLoading.value = false
  }
}

const highlightedContentHtml = computed(() => {
  const code = contentData.value.content || ''
  return hljs.highlight(code, { language: 'plaintext' }).value
})

// ==================== 配置差异对比 ====================

const showDiffModal = ref(false)
const diffData = ref<DiffResponse | null>(null)
const diffLoading = ref(false)

const handleViewDiff = async (row: Backup) => {
  diffLoading.value = true
  showDiffModal.value = true
  try {
    const res = await getDeviceLatestDiff(row.device_id)
    diffData.value = res.data
  } catch {
    showDiffModal.value = false
  } finally {
    diffLoading.value = false
  }
}

// ==================== 删除备份 ====================

const handleDelete = (row: Backup) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除该备份吗？（设备: ${row.device?.name || row.device_name || row.device_id}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteBackup(row.id)
        $alert.success('备份已删除')
        tableRef.value?.reload()
        if (showRecycleBin.value) recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleRestore = (row: Backup) => {
  dialog.warning({
    title: '确认恢复',
    content: `确定要恢复该备份吗？（设备: ${row.device?.name || row.device_name || row.device_id}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await restoreBackup(row.id)
        $alert.success('备份已恢复')
        tableRef.value?.reload()
        if (showRecycleBin.value) recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleHardDelete = (row: Backup) => {
  dialog.error({
    title: '确认彻底删除',
    content: `彻底删除后不可恢复，确定继续吗？（设备: ${row.device?.name || row.device_name || row.device_id}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await hardDeleteBackup(row.id)
        $alert.success('备份已彻底删除')
        tableRef.value?.reload()
        if (showRecycleBin.value) recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchDelete = (keys: Array<string | number>) => {
  const ids = keys.map(String)
  if (ids.length === 0) {
    $alert.warning('请选择要删除的备份')
    return
  }
  dialog.warning({
    title: '确认批量删除',
    content: `确定删除选中的 ${ids.length} 条备份吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteBackups({ backup_ids: ids })
        $alert.success(`已删除 ${res.data.success_count} 条`)
        tableRef.value?.reload()
        checkedRowKeys.value = []
        if (showRecycleBin.value) recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchRestore = () => {
  const ids = checkedRecycleBinRowKeys.value.map(String)
  if (ids.length === 0) {
    $alert.warning('请选择要恢复的备份')
    return
  }
  dialog.warning({
    title: '确认批量恢复',
    content: `确定恢复选中的 ${ids.length} 条备份吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchRestoreBackups({ backup_ids: ids })
        $alert.success(`已恢复 ${res.data.success_count} 条`)
        checkedRecycleBinRowKeys.value = []
        recycleBinTableRef.value?.reload()
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleRecycleBin = () => {
  showRecycleBin.value = true
  checkedRecycleBinRowKeys.value = []
}

const handleBatchHardDelete = () => {
  const ids = checkedRecycleBinRowKeys.value.map(String)
  if (ids.length === 0) {
    $alert.warning('请选择要彻底删除的备份')
    return
  }
  dialog.error({
    title: '确认批量彻底删除',
    content: `彻底删除后不可恢复，确定删除选中的 ${ids.length} 条备份吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchHardDeleteBackups({ backup_ids: ids })
        $alert.success(`已彻底删除 ${res.data.success_count} 条`)
        checkedRecycleBinRowKeys.value = []
        recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleMainSelectionChange = (keys: Array<string | number>) => {
  checkedRowKeys.value = keys
}

const handleRecycleSelectionChange = (keys: Array<string | number>) => {
  checkedRecycleBinRowKeys.value = keys
}

// ==================== 手动备份 ====================

const showBackupModal = ref(false)
const backupModel = ref({
  device_id: '',
})
const deviceOptions = ref<{ label: string; value: string }[]>([])
const deviceLoading = ref(false)
const deviceMap = ref<Record<string, Device>>({})

const handleManualBackup = async () => {
  deviceLoading.value = true
  showBackupModal.value = true
  try {
    const res = await getDeviceOptions({ status: 'active' })
    deviceMap.value = Object.fromEntries(res.data.items.map((d: Device) => [d.id, d]))
    deviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
  } catch {
    showBackupModal.value = false
  } finally {
    deviceLoading.value = false
  }
}

const submitManualBackup = async () => {
  if (!backupModel.value.device_id) {
    $alert.warning('请选择设备')
    return
  }

  // 1. 如果是手动 OTP 设备，预先检查并弹窗 (这里逻辑可以保留，作为前置优化)
  // ... (省略前置检查代码，因为全局拦截器是处理后端的428响应，前置检查是避免请求)
  // 实际上，如果想完全依赖全局拦截器，可以移除这里的前置检查，让请求发出去，然后被拦截器捕获
  // 但保留前置检查用户体验更好（少一次失败的请求）

  otpLoading.value = true
  try {
    await backupDevice(backupModel.value.device_id)
    $alert.success('备份任务已提交')
    showBackupModal.value = false
    tableRef.value?.reload()
  } catch {
    // 全局拦截器会自动处理 428 OTP
  } finally {
    otpLoading.value = false
  }
}

// ==================== OTP 输入处理 ====================

interface OTPRequiredDetails {
  type?: string
  message?: string
  dept_id: string
  device_group: string
  failed_devices?: string[]
  pending_device_ids?: string[]
  task_id?: string
  otp_wait_status?: string
  otp_wait_timeout?: number
  otp_cache_ttl?: number
}

const resolveOtpPayload = (error: unknown): OTPRequiredDetails | null => {
  const err = error as {
    response?: {
      data?: {
        message?: string
        details?: OTPRequiredDetails
        data?: OTPRequiredDetails | { otp_notice?: OTPRequiredDetails }
      }
    }
  }
  const data = err?.response?.data
  const dataPayload = data?.data as OTPRequiredDetails | { otp_notice?: OTPRequiredDetails } | undefined
  const candidate =
    (dataPayload as { otp_notice?: OTPRequiredDetails } | undefined)?.otp_notice ||
    (dataPayload as OTPRequiredDetails | undefined) ||
    (data?.details as OTPRequiredDetails | undefined)
  if (!candidate?.dept_id || !candidate?.device_group) return null
  return {
    dept_id: candidate.dept_id,
    device_group: candidate.device_group,
    failed_devices: candidate.failed_devices || [],
    pending_device_ids: candidate.pending_device_ids,
    task_id: candidate.task_id,
    otp_wait_status: candidate.otp_wait_status,
    otp_wait_timeout: candidate.otp_wait_timeout,
    otp_cache_ttl: candidate.otp_cache_ttl,
    message: candidate.message || data?.message,
  }
}

const showOTPModal = ref(false)
const otpLoading = ref(false)
const otpRequiredInfo = ref<OTPRequiredDetails | null>(null)
const pendingBackupDeviceId = ref<string>('')
const pendingBatchBackup = ref(false)
const currentBatchTaskId = ref('')
const otpQueue = ref<OTPRequiredDetails[]>([])
const otpQueueHint = computed(() => {
  const count = otpQueue.value.length
  if (!count) return ''
  return count === 1 ? '还有下一组 OTP 待输入' : `还有 ${count} 组 OTP 待输入`
})
const otpIdleTimeoutMs = computed(() => {
  const waitSeconds = otpRequiredInfo.value?.otp_wait_timeout
  if (typeof waitSeconds === 'number' && waitSeconds > 0) {
    return Math.floor(waitSeconds * 1000)
  }
  return 60_000
})

const submitOTP = async (otpCode: string) => {
  if (!/^\d{6}$/.test(otpCode)) {
    $alert.warning('请输入有效的 OTP 验证码（6位数字）')
    return
  }
  if (!otpRequiredInfo.value) {
    $alert.error('OTP 信息丢失，请重试')
    return
  }

  otpLoading.value = true
  try {
    // 关闭 OTP 对话框
    showOTPModal.value = false

    // 重试备份
    if (pendingBatchBackup.value) {
      // 批量备份：仍通过专用缓存接口写入 (按 dept/group)
      const cacheRequest: OTPCacheRequest = {
        dept_id: otpRequiredInfo.value.dept_id,
        device_group: otpRequiredInfo.value.device_group as OTPCacheRequest['device_group'],
        otp_code: otpCode,
      }
      await cacheOTP(cacheRequest)
      const resumeTaskId = otpRequiredInfo.value.task_id || currentBatchTaskId.value
      if (!resumeTaskId) {
        $alert.error('任务ID丢失，无法恢复')
        return
      }
      await resumeTaskGroup(resumeTaskId, {
        dept_id: otpRequiredInfo.value.dept_id,
        group: otpRequiredInfo.value.device_group,
      })
      $alert.success('OTP 已缓存，已发起恢复')
      startPollingTaskStatus(resumeTaskId)
    } else if (pendingBackupDeviceId.value) {
      // 单设备备份：直接把 otp_code 传给后端备份接口
      await backupDevice(pendingBackupDeviceId.value, { otp_code: otpCode })
      $alert.success('备份任务已提交')
      showBackupModal.value = false
      tableRef.value?.reload()
    }
  } catch {
    // Error handled by request interceptor
  } finally {
    otpLoading.value = false
    pendingBackupDeviceId.value = ''
    otpRequiredInfo.value = null
    if (otpQueue.value.length > 0) {
      applyNextOtp()
      pendingBatchBackup.value = true
    } else {
      pendingBatchBackup.value = false
    }
  }
}

const buildOtpKey = (payload: OTPRequiredDetails) =>
  `${payload.dept_id}|${payload.device_group}|${payload.task_id || ''}`

const applyNextOtp = () => {
  const next = otpQueue.value.shift()
  if (!next) return
  otpRequiredInfo.value = next
  showOTPModal.value = true
}

const enqueueOtp = (payload: OTPRequiredDetails) => {
  const nextKey = buildOtpKey(payload)
  if (otpQueue.value.some(item => buildOtpKey(item) === nextKey)) return
  if (otpRequiredInfo.value && buildOtpKey(otpRequiredInfo.value) === nextKey) {
    if (!showOTPModal.value) {
      if (otpLoading.value) {
        otpQueue.value.push(payload)
      } else {
        showOTPModal.value = true
      }
    }
    return
  }
  if (showOTPModal.value || otpLoading.value) {
    otpQueue.value.push(payload)
  } else {
    otpRequiredInfo.value = payload
    showOTPModal.value = true
  }
  pendingBatchBackup.value = true
}

const handleOtpTimeout = () => {
  showOTPModal.value = false
  otpRequiredInfo.value = null
  if (otpQueue.value.length > 0) {
    applyNextOtp()
    pendingBatchBackup.value = true
  } else {
    pendingBatchBackup.value = false
  }
}

const handleOtpModalUpdate = (v: boolean) => {
  showOTPModal.value = v
  if (v || otpLoading.value) return
  otpRequiredInfo.value = null
  if (otpQueue.value.length > 0) {
    applyNextOtp()
    pendingBatchBackup.value = true
  } else {
    pendingBatchBackup.value = false
  }
}

// ==================== 批量备份 ====================

const showBatchBackupModal = ref(false)
const batchBackupModel = ref({
  device_ids: [] as string[],
  backup_type: 'scheduled' as BackupTypeType,
})
// 存储选中的设备对象，用于 OTP 检查
const selectedBatchDevices = ref<Device[]>([])

// 使用 useTaskPolling composable
const {
  taskStatus: batchTaskStatus,
  isPolling: batchTaskPolling,
  start: startPollingTaskStatus,
  stop: stopPollingTaskStatus,
  reset: resetBatchTask,
} = useTaskPolling<BackupTaskStatus>((taskId) => getBackupTaskStatus(taskId), {
  onComplete: (status) => {
    // 任务完成后，1 秒后自动关闭弹窗并刷新列表
    if (status.status === 'success') {
      $alert.success(
        `备份完成：成功 ${status.success_count ?? 0} 台，失败 ${status.failed_count ?? 0} 台`,
      )
      setTimeout(() => {
        showBatchBackupModal.value = false
        tableRef.value?.reload()
      }, 1000)
    } else if (status.status === 'running') {
      // 检查运行中是否返回了 OTP 要求（兼容旧格式和新格式）
      // 假设新格式下，getBackupTaskStatus 正常返回 200，但 data 中包含 otp_notice
      const otpNotice = status.otp_notice
      if (otpNotice) {
        stopPollingTaskStatus()
        $alert.warning(otpNotice.message || '部分设备需要 OTP 验证码，请输入以继续')
        const payload: OTPRequiredDetails = {
          dept_id: otpNotice.dept_id,
          device_group: otpNotice.device_group,
          failed_devices: otpNotice.failed_devices?.map(d => d.name) || [],
          pending_device_ids: otpNotice.pending_device_ids,
          task_id: otpNotice.task_id,
          otp_wait_status: otpNotice.otp_wait_status,
          otp_wait_timeout: otpNotice.otp_wait_timeout,
          otp_cache_ttl: otpNotice.otp_cache_ttl,
        }
        enqueueOtp(payload)
        if (otpNotice.task_id) {
          currentBatchTaskId.value = otpNotice.task_id
        }
        if (otpNotice.pending_device_ids && otpNotice.pending_device_ids.length > 0) {
          batchBackupModel.value.device_ids = otpNotice.pending_device_ids
        }
      }
    } else if (status.status === 'failed') {
      $alert.error(`备份失败: ${status.error || '未知错误'}`)
      setTimeout(() => {
        showBatchBackupModal.value = false
      }, 2000)
    }
  },
  onError: (error) => {
    // 捕获 428 OTP_REQUIRED 错误
    const payload = resolveOtpPayload(error)
    if (!payload) return
    stopPollingTaskStatus()
    $alert.warning(payload.message || '需要输入 OTP 验证码')
    enqueueOtp(payload)
    if (payload.task_id) {
      currentBatchTaskId.value = payload.task_id
    }

    // 更新待重试设备 ID
    if (payload.pending_device_ids && payload.pending_device_ids.length > 0) {
      batchBackupModel.value.device_ids = payload.pending_device_ids
    }
  },
})

const handleBatchBackup = async () => {
  showBatchBackupModal.value = true
  resetBatchTask()
}

const submitBatchBackup = async () => {
  if (batchBackupModel.value.device_ids.length === 0) {
    $alert.warning('请选择设备')
    return
  }

  // 直接提交，由后端返回 428 触发 OTP 流程
  otpLoading.value = true
  try {
    await submitBatchBackupInternal()
  } finally {
    otpLoading.value = false
    if (!showOTPModal.value && otpQueue.value.length > 0) {
      applyNextOtp()
      pendingBatchBackup.value = true
    }
  }
}

const submitBatchBackupInternal = async () => {
  try {
    const res = await batchBackup(
      {
        device_ids: batchBackupModel.value.device_ids,
        backup_type: batchBackupModel.value.backup_type,
      },
      { skipOtpHandling: true },
    )
    $alert.success('批量备份任务已提交')
    // 开始轮询任务状态
    startPollingTaskStatus(res.data.task_id)
    currentBatchTaskId.value = res.data.task_id
  } catch (error) {
    // 由本地处理 428 OTP
    const payload = resolveOtpPayload(error)
    if (!payload) return
    $alert.warning(payload.message || '需要输入 OTP 验证码')
    enqueueOtp(payload)
    if (payload.task_id) {
      currentBatchTaskId.value = payload.task_id
    }
  }
}

const closeBatchBackupModal = () => {
  stopPollingTaskStatus()
  showBatchBackupModal.value = false
  batchBackupModel.value = { device_ids: [], backup_type: 'scheduled' }
  currentBatchTaskId.value = ''
  otpQueue.value = []
  otpRequiredInfo.value = null
  showOTPModal.value = false
  resetBatchTask()
}

onMounted(() => {
  setupAutoRefresh()
})

onUnmounted(() => {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
})

watch(autoRefresh, () => {
  setupAutoRefresh()
})

</script>

<template>
  <div class="backup-management p-4">
    <ProTable ref="tableRef" title="配置备份列表" :columns="columns" :request="loadData" :row-key="(row: Backup) => row.id"
      :context-menu-options="contextMenuOptions" search-placeholder="搜索设备名称" :search-filters="searchFilters"
      @context-menu-select="handleContextMenuSelect" @update:checked-row-keys="handleMainSelectionChange"
      @recycle-bin="handleRecycleBin" show-recycle-bin>
      <template #toolbar-left>
        <n-space>
          <n-button v-if="checkedRowKeys.length > 0" type="error" @click="handleBatchDelete(checkedRowKeys)">
            批量删除
          </n-button>
          <n-button type="primary" @click="handleManualBackup">手动备份</n-button>
          <n-button type="info" @click="handleBatchBackup">批量备份</n-button>
          <DataImportExport title="备份" show-export export-name="backups_export.csv" :export-api="exportBackups" />
          <n-button @click="handleRefresh">刷新</n-button>
          <n-space align="center" size="small">
            <span style="font-size: 12px; color: #666">自动刷新</span>
            <n-switch v-model:value="autoRefresh" />
          </n-space>
        </n-space>
      </template>
    </ProTable>

    <!-- 回收站 Modal -->
    <n-modal v-model:show="showRecycleBin" preset="card" title="回收站 (已删除备份)" style="width: 900px">
      <ProTable ref="recycleBinTableRef" title="已删除备份" :columns="columns" :request="recycleBinRequest"
        :row-key="(row: Backup) => row.id" :context-menu-options="recycleBinContextMenuOptions"
        search-placeholder="搜索设备名称" :search-filters="searchFilters"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        @update:checked-row-keys="handleRecycleSelectionChange">
        <template #toolbar-left>
          <n-space>
            <n-button type="success" :disabled="checkedRecycleBinRowKeys.length === 0" @click="handleBatchRestore">
              批量恢复
            </n-button>
            <n-button type="error" :disabled="checkedRecycleBinRowKeys.length === 0" @click="handleBatchHardDelete">
              批量彻底删除
            </n-button>
          </n-space>
        </template>
      </ProTable>
    </n-modal>

    <!-- 查看配置内容 Modal -->
    <n-modal v-model:show="showContentModal" preset="card" title="配置内容" style="width: 900px; height: 80vh">
      <div v-if="contentLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else>
        <div class="backup-modal-body">
          <div style="margin-bottom: 16px">
            <n-space>
              <span>设备: {{ contentData.device_name }}</span>
              <n-tag :type="backupTypeColorMap[contentData.backup_type]" size="small">
                {{ backupTypeLabelMap[contentData.backup_type] }}
              </n-tag>
              <span>Hash: {{ contentData.md5_hash || '-' }}</span>
              <span>时间: {{ formatDateTime(contentData.created_at) }}</span>
            </n-space>
          </div>
          <div class="backup-modal-scroll">
            <pre class="backup-code"><code class="hljs" v-html="highlightedContentHtml"></code></pre>
          </div>
        </div>
      </template>
    </n-modal>

    <!-- 配置差异 Modal -->
    <n-modal v-model:show="showDiffModal" preset="card" title="配置差异对比" style="width: 900px; height: 80vh">
      <div v-if="diffLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="diffData">
        <div class="backup-modal-body">
          <div style="margin-bottom: 16px">
            <n-space>
              <span>设备: {{ diffData.device_name }}</span>
              <n-tag v-if="diffData.has_changes" type="warning" size="small">有变更</n-tag>
              <n-tag v-else type="success" size="small">无变更</n-tag>
            </n-space>
          </div>
          <div v-if="diffData.has_changes && diffData.diff_content" class="backup-modal-scroll">
            <UnifiedDiffViewer :diff="diffData.diff_content" :max-height="'100%'" />
          </div>
          <n-alert v-else type="success" title="配置无变化">
            最新两次备份的配置内容完全一致
          </n-alert>
        </div>
      </template>
    </n-modal>

    <!-- 手动备份 Modal -->
    <n-modal v-model:show="showBackupModal" preset="dialog" title="手动备份" style="width: 500px">
      <div v-if="deviceLoading" style="text-align: center; padding: 20px">加载设备列表...</div>
      <template v-else>
        <n-select v-model:value="backupModel.device_id" :options="deviceOptions" placeholder="请选择要备份的设备" filterable />
      </template>
      <template #action>
        <n-button @click="showBackupModal = false">取消</n-button>
        <n-button type="primary" :loading="otpLoading" :disabled="otpLoading"
          @click="submitManualBackup">开始备份</n-button>
      </template>
    </n-modal>

    <!-- 批量备份 Modal -->
    <n-modal v-model:show="showBatchBackupModal" preset="card" title="批量备份" style="width: 600px"
      :closable="!batchTaskPolling" :mask-closable="!batchTaskPolling" @close="closeBatchBackupModal">
      <template v-if="batchTaskStatus">
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ batchTaskStatus.task_id }}</p>
            <p>
              状态:
              <n-tag :type="batchTaskStatus.status === 'success'
                ? 'success'
                : batchTaskStatus.status === 'failed'
                  ? 'error'
                  : 'info'
                ">
                {{ batchTaskStatus.status }}
              </n-tag>
            </p>
            <!-- 显示进度信息 -->
            <p v-if="batchTaskStatus.progress && typeof batchTaskStatus.progress === 'object'"
              style="color: #666; font-size: 12px;">
              {{ (batchTaskStatus.progress as Record<string, unknown>).message ||
                (batchTaskStatus.progress as Record<string, unknown>).stage || '执行中...' }}
            </p>
          </div>
          <n-progress type="line"
            :percentage="batchTaskStatus.percent ?? (batchTaskStatus.total ? Math.round((batchTaskStatus.completed ?? 0) / batchTaskStatus.total * 100) : 0)"
            :status="batchTaskStatus.status === 'success'
              ? 'success'
              : batchTaskStatus.status === 'failed'
                ? 'error'
                : 'default'
              " :processing="batchTaskStatus.status === 'running' || batchTaskStatus.status === 'pending'" />
          <template v-if="batchTaskStatus.status === 'success' || batchTaskStatus.status === 'failed'">
            <div>
              <p>总数: {{ batchTaskStatus.total_devices }}</p>
              <p>
                成功:
                {{ batchTaskStatus.success_count ?? 0 }}
              </p>
              <p>
                失败:
                {{ batchTaskStatus.failed_count ?? 0 }}
              </p>
            </div>
            <div v-if="batchTaskStatus.failed_devices?.length">
              <p>失败详情:</p>
              <ul>
                <li v-for="item in batchTaskStatus.failed_devices" :key="item.name">
                  设备 {{ item.name }}: {{ item.error }}
                </li>
              </ul>
            </div>
          </template>

          <n-alert v-if="batchTaskStatus.error" type="error" :title="batchTaskStatus.error" />
        </n-space>
        <div v-if="batchTaskStatus.status === 'success' || batchTaskStatus.status === 'failed'"
          style="margin-top: 20px; text-align: right">
          <n-button @click="closeBatchBackupModal">关闭</n-button>
        </div>
      </template>
      <div v-else>
        <n-space vertical style="width: 100%">
          <DeviceSelector v-model="batchBackupModel.device_ids"
            @update:devices="(devs) => (selectedBatchDevices = devs)" label="选择设备" />
          <div>
            <label style="display: block; margin-bottom: 8px">备份类型:</label>
            <n-select v-model:value="batchBackupModel.backup_type" :options="backupTypeOptions" />
          </div>
        </n-space>
        <div style="margin-top: 20px; text-align: right">
          <n-space>
            <n-button @click="closeBatchBackupModal">取消</n-button>
            <n-button type="primary" :loading="otpLoading" :disabled="otpLoading"
              @click="submitBatchBackup">开始批量备份</n-button>
          </n-space>
        </div>
      </div>
    </n-modal>

    <!-- OTP 输入 Modal（通用组件） -->
    <OtpModal :show="showOTPModal" :loading="otpLoading" :idle-timeout-ms="otpIdleTimeoutMs"
      :queue-hint="otpQueueHint"
      title="需要 OTP 验证码" alert-title="设备需要 OTP 认证"
      alert-text="请输入当前有效的 OTP 验证码以继续操作。" :info-items="otpRequiredInfo
        ? [
          {
            label: '设备分组',
            value:
              deviceGroupLabels[otpRequiredInfo.device_group] || otpRequiredInfo.device_group,
          },
        ]
        : []
        " confirm-text="确认" @confirm="submitOTP" @timeout="handleOtpTimeout"
      @update:show="handleOtpModalUpdate" />
  </div>
</template>

<style scoped>
.backup-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}

.backup-modal-body {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.backup-modal-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  max-height: calc(80vh - 140px);
}

.backup-code {
  margin: 0;
  white-space: pre;
}

.otp-center {
  width: 100%;
  display: flex;
  justify-content: center;
}
</style>
