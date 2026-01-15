<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NFormItem,
  NInput,
  NModal,
  useDialog,
  type DataTableColumns,
  NTag,
  NSelect,
  NTreeSelect,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getCredentials,
  createCredential,
  updateCredential,
  deleteCredential,
  cacheOTP,
  batchDeleteCredentials,
  getRecycleBinCredentials,
  restoreCredential,
  batchRestoreCredentials,
  hardDeleteCredential,
  batchHardDeleteCredentials,
  type Credential,
  type CredentialSearchParams,
} from '@/api/credentials'
import { DeviceGroup, AuthType, type DeviceGroupType } from '@/types/enums'
import {
  DeviceGroupOptions,
  AuthTypeOptions,
  DeviceGroupLabels,
  AuthTypeLabels,
} from '@/types/enum-labels'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'

defineOptions({
  name: 'CredentialManagement',
})

const dialog = useDialog()
const tableRef = ref()
const selectedRowKeys = ref<string[]>([])

// ==================== 回收站 ====================

const showRecycleBin = ref(false)
const recycleBinRef = ref()

const recycleBinColumns: DataTableColumns<Credential> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '所属部门',
    key: 'dept_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.dept_name || '-',
  },
  {
    title: '设备分组',
    key: 'device_group',
    width: 120,
    render: (row) => groupLabelMap[row.device_group],
  },
  { title: 'SSH 用户名', key: 'username', width: 150 },
  {
    title: '认证类型',
    key: 'auth_type',
    width: 120,
    render(row) {
      return h(
        NTag,
        { type: row.auth_type === 'static' ? 'default' : 'info', bordered: false },
        { default: () => authTypeLabelMap[row.auth_type] },
      )
    },
  },
  {
    title: '删除时间',
    key: 'updated_at',
    width: 180,
    render: (row) => formatDateTime(row.updated_at),
  },
]

const loadRecycleBinData = async (params: { page?: number; page_size?: number; keyword?: string }) => {
  const res = await getRecycleBinCredentials(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleRestore = async (row: Credential) => {
  try {
    await restoreCredential(row.id)
    $alert.success('凭据已恢复')
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleBatchRestore = async (ids: string[]) => {
  try {
    const res = await batchRestoreCredentials(ids)
    $alert.success(`成功恢复 ${res.data.success_count} 条凭据`)
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleHardDelete = async (row: Credential) => {
  try {
    await hardDeleteCredential(row.id)
    $alert.success('凭据已彻底删除')
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleBatchHardDelete = async (ids: string[]) => {
  try {
    const res = await batchHardDeleteCredentials(ids)
    $alert.success(`成功彻底删除 ${res.data.success_count} 条凭据`)
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 常量定义（使用统一枚举） ====================

const deviceGroupOptions = DeviceGroupOptions
const authTypeOptions = AuthTypeOptions
const groupLabelMap = DeviceGroupLabels
const authTypeLabelMap = AuthTypeLabels

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

const columns: DataTableColumns<Credential> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '所属部门',
    key: 'dept_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.dept_name || '-',
  },
  {
    title: '设备分组',
    key: 'device_group',
    width: 120,
    render: (row) => groupLabelMap[row.device_group],
  },
  { title: 'SSH 用户名', key: 'username', width: 150 },
  {
    title: '认证类型',
    key: 'auth_type',
    width: 120,
    render(row) {
      return h(
        NTag,
        { type: row.auth_type === 'static' ? 'default' : 'info', bordered: false },
        { default: () => authTypeLabelMap[row.auth_type] },
      )
    },
  },
  {
    title: '描述',
    key: 'description',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => row.description || '-',
  },
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
  { key: 'device_group', placeholder: '设备分组', options: deviceGroupOptions, width: 120 },
]

// ==================== 数据加载 ====================

const loadData = async (params: CredentialSearchParams) => {
  const res = await getCredentials(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '缓存 OTP', key: 'cache_otp' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Credential) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
  if (key === 'cache_otp') handleCacheOTP(row)
}

// ==================== 批量删除 ====================

const handleBatchDelete = () => {
  if (selectedRowKeys.value.length === 0) {
    $alert.warning('请先选择要删除的凭据')
    return
  }
  dialog.warning({
    title: '确认批量删除',
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 条凭据吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteCredentials(selectedRowKeys.value)
        $alert.success(`成功删除 ${res.data.success_count} 条凭据`)
        selectedRowKeys.value = []
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 创建/编辑凭据 ====================

const modalType = ref<'create' | 'edit'>('create')
const showCreateModal = ref(false)
const createFormRef = ref()
const createModel = ref({
  id: '',
  dept_id: '' as string,
  device_group: DeviceGroup.CORE as `${DeviceGroup}`,
  username: '',
  otp_seed: '',
  auth_type: AuthType.OTP_SEED as `${AuthType}`,
  description: '',
})

const createRules = {
  dept_id: { required: true, message: '请选择部门', trigger: 'change' },
  device_group: { required: true, message: '请选择设备分组', trigger: 'change' },
  username: { required: true, message: '请输入SSH用户名', trigger: 'blur' },
}

const handleCreate = () => {
  modalType.value = 'create'
  createModel.value = {
    id: '',
    dept_id: '',
    device_group: DeviceGroup.CORE,
    username: '',
    otp_seed: '',
    auth_type: AuthType.OTP_SEED,
    description: '',
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const handleEdit = (row: Credential) => {
  modalType.value = 'edit'
  createModel.value = {
    id: row.id,
    dept_id: row.dept_id,
    device_group: row.device_group,
    username: row.username,
    otp_seed: '',
    auth_type: row.auth_type,
    description: row.description || '',
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const submitCreate = (e: MouseEvent) => {
  e.preventDefault()
  createFormRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        if (modalType.value === 'create') {
          await createCredential({
            dept_id: createModel.value.dept_id,
            device_group: createModel.value.device_group,
            username: createModel.value.username,
            otp_seed: createModel.value.otp_seed || undefined,
            auth_type: createModel.value.auth_type,
            description: createModel.value.description || undefined,
          })
          $alert.success('凭据创建成功')
        } else {
          await updateCredential(createModel.value.id, {
            username: createModel.value.username,
            otp_seed: createModel.value.otp_seed || undefined,
            auth_type: createModel.value.auth_type,
            description: createModel.value.description || undefined,
          })
          $alert.success('凭据更新成功')
        }
        showCreateModal.value = false
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    }
  })
}

// ==================== 删除凭据 ====================

const handleDelete = (row: Credential) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除该凭据吗？（部门: ${row.dept_name}, 分组: ${groupLabelMap[row.device_group]}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteCredential(row.id)
        $alert.success('凭据已删除')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 缓存 OTP ====================

const showOTPModal = ref(false)
const otpModel = ref({
  dept_id: '',
  device_group: DeviceGroup.CORE as DeviceGroupType,
  otp_code: '',
  dept_name: '',
})

const handleCacheOTP = (row: Credential) => {
  otpModel.value = {
    dept_id: row.dept_id,
    device_group: row.device_group,
    otp_code: '',
    dept_name: row.dept_name || '',
  }
  showOTPModal.value = true
}

const submitCacheOTP = async () => {
  if (!otpModel.value.otp_code) {
    $alert.warning('请输入 OTP 验证码')
    return
  }
  try {
    const res = await cacheOTP({
      dept_id: otpModel.value.dept_id,
      device_group: otpModel.value.device_group,
      otp_code: otpModel.value.otp_code,
    })
    if (res.data.success) {
      $alert.success(res.data.message || `OTP 已缓存，有效期 ${res.data.expires_in} 秒`)
      showOTPModal.value = false
    } else {
      $alert.error(res.data.message || 'OTP 缓存失败')
    }
  } catch {
    // Error handled
  }
}
</script>

<template>
  <div class="credential-management p-4">
    <ProTable
      ref="tableRef"
      title="凭据列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Credential) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/描述"
      :search-filters="searchFilters"
      v-model:checked-row-keys="selectedRowKeys"
      @add="handleCreate"
      @context-menu-select="handleContextMenuSelect"
      show-add
      :scroll-x="1200"
    >
      <template #toolbar>
        <n-button
          type="error"
          :disabled="selectedRowKeys.length === 0"
          @click="handleBatchDelete"
        >
          批量删除
        </n-button>
        <n-button @click="showRecycleBin = true">回收站</n-button>
      </template>
    </ProTable>

    <!-- 回收站 Modal -->
    <RecycleBinModal
      ref="recycleBinRef"
      v-model:show="showRecycleBin"
      title="回收站 (已删除凭据)"
      :columns="recycleBinColumns"
      :request="loadRecycleBinData"
      :row-key="(row: Credential) => row.id"
      search-placeholder="搜索用户名/描述..."
      :scroll-x="900"
      @restore="handleRestore"
      @batch-restore="handleBatchRestore"
      @hard-delete="handleHardDelete"
      @batch-hard-delete="handleBatchHardDelete"
    />

    <!-- 创建/编辑凭据 Modal -->
    <n-modal
      v-model:show="showCreateModal"
      preset="dialog"
      :title="modalType === 'create' ? '新建凭据' : '编辑凭据'"
      style="width: 500px"
    >
      <n-form
        ref="createFormRef"
        :model="createModel"
        :rules="createRules"
        label-placement="left"
        label-width="100"
      >
        <n-form-item label="所属部门" path="dept_id">
          <n-tree-select
            v-model:value="createModel.dept_id"
            :options="deptTreeOptions"
            placeholder="请选择部门"
            :disabled="modalType === 'edit'"
            key-field="key"
            label-field="label"
          />
        </n-form-item>
        <n-form-item label="设备分组" path="device_group">
          <n-select
            v-model:value="createModel.device_group"
            :options="deviceGroupOptions"
            placeholder="请选择设备分组"
            :disabled="modalType === 'edit'"
          />
        </n-form-item>
        <n-form-item label="SSH 用户名" path="username">
          <n-input v-model:value="createModel.username" placeholder="请输入SSH用户名" />
        </n-form-item>
        <n-form-item label="OTP 种子">
          <n-input
            v-model:value="createModel.otp_seed"
            type="password"
            show-password-on="click"
            placeholder="OTP 种子（留空则保持不变）"
          />
        </n-form-item>
        <n-form-item label="认证类型">
          <n-select
            v-model:value="createModel.auth_type"
            :options="authTypeOptions"
            placeholder="请选择认证类型"
          />
        </n-form-item>
        <n-form-item label="描述">
          <n-input
            v-model:value="createModel.description"
            type="textarea"
            placeholder="凭据描述"
            :rows="2"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showCreateModal = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">提交</n-button>
      </template>
    </n-modal>

    <!-- 缓存 OTP Modal -->
    <n-modal v-model:show="showOTPModal" preset="dialog" title="缓存 OTP 验证码" style="width: 400px">
      <div style="margin-bottom: 16px">
        <p>部门: {{ otpModel.dept_name }}</p>
        <p>设备分组: {{ groupLabelMap[otpModel.device_group] }}</p>
      </div>
      <n-form label-placement="left" label-width="100">
        <n-form-item label="OTP 验证码">
          <n-input
            v-model:value="otpModel.otp_code"
            placeholder="请输入6位OTP验证码"
            maxlength="6"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showOTPModal = false">取消</n-button>
        <n-button type="primary" @click="submitCacheOTP">缓存</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.credential-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
