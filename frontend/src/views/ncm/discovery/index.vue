<script setup lang="ts">
import { ref, h } from 'vue'
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
  NProgress,
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
  adoptDevice,
  getShadowAssets,
  getOfflineDevices,
  compareCMDB,
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
import { useTaskPolling } from '@/composables'

defineOptions({
  name: 'DiscoveryManagement',
})

const dialog = useDialog()
const tableRef = ref()

// ==================== 常量定义 ====================

const statusOptions = [
  { label: '新发现', value: 'new' },
  { label: '已忽略', value: 'ignored' },
  { label: '已匹配', value: 'matched' },
]

const statusLabelMap: Record<DiscoveryStatus, string> = {
  new: '新发现',
  ignored: '已忽略',
  matched: '已匹配',
}

const statusColorMap: Record<DiscoveryStatus, 'info' | 'default' | 'success'> = {
  new: 'info',
  ignored: 'default',
  matched: 'success',
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

// ==================== 表格列定义 ====================

const columns: DataTableColumns<DiscoveryRecord> = [
  { type: 'selection', fixed: 'left' },
  { title: 'IP 地址', key: 'ip_address', width: 140, fixed: 'left' },
  { title: 'MAC 地址', key: 'mac_address', width: 150, render: (row) => row.mac_address || '-' },
  { title: '厂商', key: 'vendor', width: 100, ellipsis: { tooltip: true }, render: (row) => row.vendor || '-' },
  { title: '主机名', key: 'hostname', width: 150, ellipsis: { tooltip: true }, render: (row) => row.hostname || '-' },
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
    title: '首次发现',
    key: 'first_seen_at',
    width: 160,
    render: (row) => formatDateTime(row.first_seen_at),
  },
  {
    title: '最后发现',
    key: 'last_seen_at',
    width: 160,
    render: (row) => formatDateTime(row.last_seen_at),
  },
  { title: '离线天数', key: 'offline_days', width: 90 },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: DiscoverySearchParams) => {
  const res = await getDiscoveryRecords(params)
  return {
    data: res.items,
    total: res.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '纳管设备', key: 'adopt' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: DiscoveryRecord) => {
  if (key === 'adopt') handleAdopt(row)
  if (key === 'delete') handleDelete(row)
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
    name: row.hostname || row.ip_address,
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
  scan_type: 'nmap' as 'nmap' | 'masscan',
  ports: '22,23,80,443',
  async_mode: true,
})

// 使用 useTaskPolling composable
const {
  taskStatus: scanTaskStatus,
  start: startPollingScanStatus,
  stop: stopPollingScanStatus,
  reset: resetScanTask,
} = useTaskPolling<ScanTaskStatus>(
  (taskId) => getScanTaskStatus(taskId),
  {
    onComplete: () => tableRef.value?.reload(),
    onError: () => tableRef.value?.reload(),
  }
)

const handleTriggerScan = () => {
  scanModel.value = {
    subnets: '',
    scan_type: 'nmap',
    ports: '22,23,80,443',
    async_mode: true,
  }
  resetScanTask()
  showScanModal.value = true
}

const submitScan = async () => {
  if (!scanModel.value.subnets) {
    $alert.warning('请输入扫描网段')
    return
  }
  const subnets = scanModel.value.subnets.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)
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
    })
    if (res.data.task_id) {
      $alert.success('扫描任务已提交')
      startPollingScanStatus(res.data.task_id)
    } else if (res.data.result) {
      $alert.success('扫描完成')
      tableRef.value?.reload()
    }
  } catch {
    // Error handled
  }
}

const closeScanModal = () => {
  stopPollingScanStatus()
  showScanModal.value = false
  scanTaskStatus.value = null
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
    shadowAssets.value = shadowRes.items || []
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
      :scroll-x="1400"
    >
      <template #toolbar-left>
        <n-space>
          <n-button type="primary" @click="handleTriggerScan">触发扫描</n-button>
          <n-button type="info" @click="handleShowExtra">影子资产/离线设备</n-button>
          <n-button @click="handleCompareCMDB">CMDB 比对</n-button>
        </n-space>
      </template>
    </ProTable>

    <!-- 触发扫描 Modal -->
    <n-modal
      v-model:show="showScanModal"
      preset="card"
      title="触发网络扫描"
      style="width: 600px"
      :closable="!scanTaskPolling"
      :mask-closable="!scanTaskPolling"
      @close="closeScanModal"
    >
      <template v-if="!scanTaskStatus">
        <n-space vertical style="width: 100%">
          <n-form-item label="扫描网段 (每行一个或逗号分隔)">
            <n-input
              v-model:value="scanModel.subnets"
              type="textarea"
              placeholder="例如: 192.168.1.0/24, 10.0.0.0/24"
              :rows="3"
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
      </template>
      <template v-else>
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ scanTaskStatus.task_id }}</p>
            <p>
              状态:
              <n-tag
                :type="
                  scanTaskStatus.status === 'SUCCESS'
                    ? 'success'
                    : scanTaskStatus.status === 'FAILURE'
                      ? 'error'
                      : 'info'
                "
              >
                {{ scanTaskStatus.status }}
              </n-tag>
            </p>
          </div>
          <n-progress
            v-if="scanTaskStatus.progress !== null"
            type="line"
            :percentage="scanTaskStatus.progress"
            :status="
              scanTaskStatus.status === 'SUCCESS'
                ? 'success'
                : scanTaskStatus.status === 'FAILURE'
                  ? 'error'
                  : 'default'
            "
          />
          <template v-if="scanTaskStatus.result">
            <div style="text-align: center">
              <p>总主机数: {{ scanTaskStatus.result.total_hosts }}</p>
              <p>在线主机: {{ scanTaskStatus.result.online_hosts }}</p>
              <p>新发现: {{ scanTaskStatus.result.new_hosts }}</p>
              <p>已匹配: {{ scanTaskStatus.result.matched_hosts }}</p>
            </div>
          </template>
          <n-alert v-if="scanTaskStatus.error" type="error" :title="scanTaskStatus.error" />
        </n-space>
        <div
          v-if="scanTaskStatus.status === 'SUCCESS' || scanTaskStatus.status === 'FAILURE'"
          style="margin-top: 20px; text-align: right"
        >
          <n-button @click="closeScanModal">关闭</n-button>
        </div>
      </template>
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
</style>
