<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import {
  NButton,
  NFormItem,
  NInput,
  NModal,
  NInputNumber,
  useDialog,
  type DataTableColumns,
  NTag,
  NSelect,
  NTreeSelect,
  NSpace,
  NStatistic,
  NCard,
  NGrid,
  NGridItem,
  NDatePicker,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  batchDeleteDevices,
  getRecycleBinDevices,
  restoreDevice,
  transitionDeviceStatus,
  batchTransitionDeviceStatus,
  getDeviceLifecycleStats,
  type Device,
  type DeviceSearchParams,
  type DeviceLifecycleStatsResponse,
} from '@/api/devices'
import { DeviceVendor, DeviceStatus, DeviceGroup, AuthType } from '@/types/enums'
import {
  DeviceVendorOptions,
  DeviceStatusOptions,
  DeviceGroupOptions,
  AuthTypeOptions,
  DeviceVendorLabels,
  DeviceStatusLabels,
  DeviceGroupLabels,
  DeviceStatusColors,
} from '@/types/enum-labels'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'DeviceManagement',
})

const dialog = useDialog()
const tableRef = ref()
const recycleBinTableRef = ref()

// ==================== 常量定义（使用统一枚举） ====================

const vendorOptions = DeviceVendorOptions
const statusOptions = DeviceStatusOptions
const deviceGroupOptions = DeviceGroupOptions
const authTypeOptions = AuthTypeOptions
const statusColorMap = DeviceStatusColors
const statusLabelMap = DeviceStatusLabels
const vendorLabelMap = DeviceVendorLabels
const groupLabelMap = DeviceGroupLabels

// ==================== 生命周期统计 ====================

const lifecycleStats = ref<DeviceLifecycleStatsResponse>({
  stock: 0,
  running: 0,
  maintenance: 0,
  retired: 0,
  total: 0,
})

const fetchLifecycleStats = async () => {
  try {
    const res = await getDeviceLifecycleStats()
    lifecycleStats.value = res.data
  } catch {
    // Error handled
  }
}

onMounted(() => {
  fetchLifecycleStats()
})

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

const columns: DataTableColumns<Device> = [
  { type: 'selection', fixed: 'left' },
  { title: '设备名称', key: 'name', width: 150, fixed: 'left', ellipsis: { tooltip: true } },
  { title: 'IP 地址', key: 'ip_address', width: 140 },
  {
    title: '厂商',
    key: 'vendor',
    width: 100,
    render: (row) => (row.vendor ? vendorLabelMap[row.vendor] : '-'),
  },
  { title: '型号', key: 'model', width: 120, ellipsis: { tooltip: true } },
  {
    title: '设备分组',
    key: 'device_group',
    width: 100,
    render: (row) => (row.device_group ? groupLabelMap[row.device_group] : '-'),
  },
  {
    title: '所属部门',
    key: 'dept',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => row.dept?.name || '-',
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: statusColorMap[row.status], bordered: false },
        { default: () => statusLabelMap[row.status] },
      )
    },
  },
  { title: '位置', key: 'location', width: 120, ellipsis: { tooltip: true } },
  { title: '序列号', key: 'serial_number', width: 140, ellipsis: { tooltip: true } },
  { title: 'SSH端口', key: 'ssh_port', width: 90 },
  {
    title: '创建时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render: (row) => formatDateTime(row.updated_at),
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'vendor', placeholder: '厂商', options: vendorOptions, width: 120 },
  { key: 'status', placeholder: '状态', options: statusOptions, width: 120 },
  { key: 'device_group', placeholder: '设备分组', options: deviceGroupOptions, width: 120 },
]

// ==================== 数据加载 ====================

const loadData = async (params: DeviceSearchParams) => {
  const res = await getDevices(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '状态流转', key: 'transition' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Device) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
  if (key === 'transition') handleTransition(row)
}

// ==================== 创建/编辑设备 ====================

const modalType = ref<'create' | 'edit'>('create')
const showCreateModal = ref(false)
const createFormRef = ref()
const createModel = ref({
  id: '',
  name: '',
  ip_address: '',
  vendor: null as DeviceVendor | null,
  model: '',
  platform: '',
  location: '',
  description: '',
  ssh_port: 22,
  auth_type: AuthType.OTP_SEED as `${AuthType}`,
  dept_id: null as string | null,
  device_group: null as `${DeviceGroup}` | null,
  status: DeviceStatus.IN_STOCK as `${DeviceStatus}`,
  username: '',
  password: '',
  serial_number: '',
  os_version: '',
  stock_in_at: null as number | null,
  assigned_to: '',
})

const createRules = {
  name: { required: true, message: '请输入设备名称', trigger: 'blur' },
  ip_address: { required: true, message: '请输入IP地址', trigger: 'blur' },
}

const handleCreate = () => {
  modalType.value = 'create'
  createModel.value = {
    id: '',
    name: '',
    ip_address: '',
    vendor: null,
    model: '',
    platform: '',
    location: '',
    description: '',
    ssh_port: 22,
    auth_type: AuthType.OTP_SEED,
    dept_id: null,
    device_group: null,
    status: DeviceStatus.IN_STOCK,
    username: '',
    password: '',
    serial_number: '',
    os_version: '',
    stock_in_at: null,
    assigned_to: '',
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const handleEdit = (row: Device) => {
  modalType.value = 'edit'
  createModel.value = {
    id: row.id,
    name: row.name,
    ip_address: row.ip_address,
    vendor: row.vendor,
    model: row.model || '',
    platform: row.platform || '',
    location: row.location || '',
    description: row.description || '',
    ssh_port: row.ssh_port,
    auth_type: row.auth_type,
    dept_id: row.dept_id,
    device_group: row.device_group,
    status: row.status,
    username: '',
    password: '',
    serial_number: row.serial_number || '',
    os_version: row.os_version || '',
    stock_in_at: row.stock_in_at ? new Date(row.stock_in_at).getTime() : null,
    assigned_to: row.assigned_to || '',
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const submitCreate = (e: MouseEvent) => {
  e.preventDefault()
  createFormRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        const data = {
          ...createModel.value,
          vendor: createModel.value.vendor || undefined,
          device_group: createModel.value.device_group || undefined,
          dept_id: createModel.value.dept_id || undefined,
          stock_in_at: createModel.value.stock_in_at
            ? new Date(createModel.value.stock_in_at).toISOString()
            : undefined,
        }
        if (modalType.value === 'create') {
          await createDevice(data)
          $alert.success('设备创建成功')
        } else {
          await updateDevice(createModel.value.id, data)
          $alert.success('设备更新成功')
        }
        showCreateModal.value = false
        tableRef.value?.reload()
        fetchLifecycleStats()
      } catch {
        // Error handled
      }
    }
  })
}

// ==================== 删除设备 ====================

const handleDelete = (row: Device) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除设备 ${row.name} 吗？设备将被移入回收站。`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteDevice(row.id)
        $alert.success('设备已删除')
        tableRef.value?.reload()
        fetchLifecycleStats()
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchDelete = (ids: Array<string | number>) => {
  dialog.warning({
    title: '批量删除',
    content: `确定要删除选中的 ${ids.length} 个设备吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteDevices(ids as string[])
        $alert.success('批量删除成功')
        tableRef.value?.reload()
        fetchLifecycleStats()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 状态流转 ====================

const showTransitionModal = ref(false)
const transitionModel = ref({
  id: '',
  name: '',
  currentStatus: '' as DeviceStatus,
  toStatus: '' as DeviceStatus,
  reason: '',
})

const handleTransition = (row: Device) => {
  transitionModel.value = {
    id: row.id,
    name: row.name,
    currentStatus: row.status,
    toStatus: row.status,
    reason: '',
  }
  showTransitionModal.value = true
}

const submitTransition = async () => {
  if (transitionModel.value.toStatus === transitionModel.value.currentStatus) {
    $alert.warning('状态未变更')
    return
  }
  try {
    await transitionDeviceStatus(
      transitionModel.value.id,
      transitionModel.value.toStatus,
      transitionModel.value.reason || undefined,
    )
    $alert.success('状态流转成功')
    showTransitionModal.value = false
    tableRef.value?.reload()
    fetchLifecycleStats()
  } catch {
    // Error handled
  }
}

// 批量状态流转
const showBatchTransitionModal = ref(false)
const batchTransitionModel = ref({
  ids: [] as string[],
  toStatus: DeviceStatus.ACTIVE as `${DeviceStatus}`,
  reason: '',
})

const handleBatchTransition = () => {
  const selectedKeys = tableRef.value?.getSelectedKeys() || []
  if (selectedKeys.length === 0) {
    $alert.warning('请先选择设备')
    return
  }
  batchTransitionModel.value = {
    ids: selectedKeys as string[],
    toStatus: DeviceStatus.ACTIVE,
    reason: '',
  }
  showBatchTransitionModal.value = true
}

const submitBatchTransition = async () => {
  try {
    await batchTransitionDeviceStatus(
      batchTransitionModel.value.ids,
      batchTransitionModel.value.toStatus,
      batchTransitionModel.value.reason || undefined,
    )
    $alert.success('批量状态流转成功')
    showBatchTransitionModal.value = false
    tableRef.value?.reload()
    fetchLifecycleStats()
  } catch {
    // Error handled
  }
}

// ==================== 回收站 ====================

const showRecycleBin = ref(false)
const checkedRecycleBinRowKeys = ref<Array<string | number>>([])

const handleRecycleBin = () => {
  showRecycleBin.value = true
  checkedRecycleBinRowKeys.value = []
}

const recycleBinRequest = async (params: DeviceSearchParams) => {
  const res = await getRecycleBinDevices(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const recycleBinContextMenuOptions: DropdownOption[] = [
  { label: '恢复', key: 'restore' },
]

const handleRecycleBinContextMenuSelect = async (key: string | number, row: Device) => {
  if (key === 'restore') {
    try {
      await restoreDevice(row.id)
      $alert.success('设备已恢复')
      recycleBinTableRef.value?.reload()
      tableRef.value?.reload()
      fetchLifecycleStats()
    } catch {
      // Error handled
    }
  }
}

const handleBatchRestore = async () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  try {
    for (const id of checkedRecycleBinRowKeys.value) {
      await restoreDevice(id as string)
    }
    $alert.success('批量恢复成功')
    checkedRecycleBinRowKeys.value = []
    recycleBinTableRef.value?.reload()
    tableRef.value?.reload()
    fetchLifecycleStats()
  } catch {
    // Error handled
  }
}
</script>

<template>
  <div class="device-management p-4">
    <!-- 生命周期统计卡片 -->
    <n-card class="stats-card" :bordered="false" size="small">
      <n-grid :cols="5" :x-gap="16">
        <n-grid-item>
          <n-statistic label="总设备数" :value="lifecycleStats.total" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="入库">
            <template #default>
              <span style="color: #909399">{{ lifecycleStats.stock }}</span>
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="运行中">
            <template #default>
              <span style="color: #18a058">{{ lifecycleStats.running }}</span>
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="维护中">
            <template #default>
              <span style="color: #f0a020">{{ lifecycleStats.maintenance }}</span>
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="已报废">
            <template #default>
              <span style="color: #d03050">{{ lifecycleStats.retired }}</span>
            </template>
          </n-statistic>
        </n-grid-item>
      </n-grid>
    </n-card>

    <!-- 设备列表 -->
    <ProTable
      ref="tableRef"
      title="设备列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Device) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索设备名称/IP/序列号"
      :search-filters="searchFilters"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-recycle-bin
      show-batch-delete
      :scroll-x="1800"
    >
      <template #toolbar-left>
        <n-button type="info" @click="handleBatchTransition"> 批量状态流转 </n-button>
      </template>
    </ProTable>

    <!-- 回收站 Modal -->
    <n-modal
      v-model:show="showRecycleBin"
      preset="card"
      title="回收站 (已删除设备)"
      style="width: 900px"
    >
      <ProTable
        ref="recycleBinTableRef"
        :columns="columns"
        :request="recycleBinRequest"
        :row-key="(row: Device) => row.id"
        search-placeholder="搜索已删除设备..."
        :context-menu-options="recycleBinContextMenuOptions"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        v-model:checked-row-keys="checkedRecycleBinRowKeys"
        :scroll-x="1800"
      >
        <template #toolbar-left>
          <n-button
            type="success"
            :disabled="checkedRecycleBinRowKeys.length === 0"
            @click="handleBatchRestore"
          >
            批量恢复
          </n-button>
        </template>
      </ProTable>
    </n-modal>

    <!-- 创建/编辑设备 Modal -->
    <n-modal
      v-model:show="showCreateModal"
      preset="dialog"
      :title="modalType === 'create' ? '新建设备' : '编辑设备'"
      style="width: 700px"
    >
      <n-form
        ref="createFormRef"
        :model="createModel"
        :rules="createRules"
        label-placement="left"
        label-width="100"
      >
        <n-grid :cols="2" :x-gap="16">
          <n-grid-item>
            <n-form-item label="设备名称" path="name">
              <n-input v-model:value="createModel.name" placeholder="请输入设备名称" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="IP 地址" path="ip_address">
              <n-input v-model:value="createModel.ip_address" placeholder="请输入IP地址" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="厂商">
              <n-select
                v-model:value="createModel.vendor"
                :options="vendorOptions"
                placeholder="请选择厂商"
                clearable
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="型号">
              <n-input v-model:value="createModel.model" placeholder="请输入型号" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="设备分组">
              <n-select
                v-model:value="createModel.device_group"
                :options="deviceGroupOptions"
                placeholder="请选择设备分组"
                clearable
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="所属部门">
              <n-tree-select
                v-model:value="createModel.dept_id"
                :options="deptTreeOptions"
                placeholder="请选择部门"
                clearable
                key-field="key"
                label-field="label"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="SSH 端口">
              <n-input-number
                v-model:value="createModel.ssh_port"
                :min="1"
                :max="65535"
                style="width: 100%"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="认证类型">
              <n-select
                v-model:value="createModel.auth_type"
                :options="authTypeOptions"
                placeholder="请选择认证类型"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item v-if="createModel.auth_type === 'static'">
            <n-form-item label="用户名">
              <n-input v-model:value="createModel.username" placeholder="SSH 用户名" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item v-if="createModel.auth_type === 'static'">
            <n-form-item label="密码">
              <n-input
                v-model:value="createModel.password"
                type="password"
                show-password-on="click"
                placeholder="SSH 密码"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="序列号">
              <n-input v-model:value="createModel.serial_number" placeholder="设备序列号" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="系统版本">
              <n-input v-model:value="createModel.os_version" placeholder="操作系统版本" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="物理位置">
              <n-input v-model:value="createModel.location" placeholder="机房位置" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="领用人">
              <n-input v-model:value="createModel.assigned_to" placeholder="设备领用人" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="入库时间">
              <n-date-picker
                v-model:value="createModel.stock_in_at"
                type="date"
                clearable
                style="width: 100%"
              />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="状态">
              <n-select v-model:value="createModel.status" :options="statusOptions" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item :span="2">
            <n-form-item label="描述">
              <n-input
                v-model:value="createModel.description"
                type="textarea"
                placeholder="设备描述"
                :rows="2"
              />
            </n-form-item>
          </n-grid-item>
        </n-grid>
      </n-form>
      <template #action>
        <n-button @click="showCreateModal = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">提交</n-button>
      </template>
    </n-modal>

    <!-- 状态流转 Modal -->
    <n-modal v-model:show="showTransitionModal" preset="dialog" title="设备状态流转">
      <div style="margin-bottom: 16px">
        <span>设备: {{ transitionModel.name }}</span>
        <br />
        <span>当前状态: {{ statusLabelMap[transitionModel.currentStatus] }}</span>
      </div>
      <n-form label-placement="left" label-width="80">
        <n-form-item label="目标状态">
          <n-select v-model:value="transitionModel.toStatus" :options="statusOptions" />
        </n-form-item>
        <n-form-item label="变更原因">
          <n-input
            v-model:value="transitionModel.reason"
            type="textarea"
            placeholder="请输入变更原因（可选）"
            :rows="2"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showTransitionModal = false">取消</n-button>
        <n-button type="primary" @click="submitTransition">确认</n-button>
      </template>
    </n-modal>

    <!-- 批量状态流转 Modal -->
    <n-modal v-model:show="showBatchTransitionModal" preset="dialog" title="批量状态流转">
      <div style="margin-bottom: 16px">
        <span>已选择 {{ batchTransitionModel.ids.length }} 个设备</span>
      </div>
      <n-form label-placement="left" label-width="80">
        <n-form-item label="目标状态">
          <n-select v-model:value="batchTransitionModel.toStatus" :options="statusOptions" />
        </n-form-item>
        <n-form-item label="变更原因">
          <n-input
            v-model:value="batchTransitionModel.reason"
            type="textarea"
            placeholder="请输入变更原因（可选）"
            :rows="2"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showBatchTransitionModal = false">取消</n-button>
        <n-button type="primary" @click="submitBatchTransition">确认</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.device-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.p-4 {
  padding: 16px;
}

.stats-card {
  border-radius: 8px;
}
</style>
