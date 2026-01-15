<script setup lang="ts">
import { ref, h, computed, onMounted, reactive } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NTag,
  NTreeSelect,
  useDialog,
  type DataTableColumns,
  type DropdownOption,
  type FormRules,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import {
  createSnmpCredential,
  deleteSnmpCredential,
  getSnmpCredentials,
  updateSnmpCredential,
  batchDeleteSnmpCredentials,
  getRecycleBinSnmpCredentials,
  restoreSnmpCredential,
  batchRestoreSnmpCredentials,
  hardDeleteSnmpCredential,
  batchHardDeleteSnmpCredentials,
  type DeptSnmpCredential,
  type SnmpCredentialSearchParams,
  type SnmpVersion,
} from '@/api/snmp_credentials'
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'

defineOptions({
  name: 'SnmpCredentials',
})

const dialog = useDialog()
const tableRef = ref()
const selectedRowKeys = ref<string[]>([])

// ==================== 回收站 ====================

const showRecycleBin = ref(false)
const recycleBinRef = ref()

const recycleBinColumns: DataTableColumns<DeptSnmpCredential> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '所属部门',
    key: 'dept_name',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.dept_name || '-',
  },
  {
    title: 'SNMP 版本',
    key: 'snmp_version',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { type: row.snmp_version === 'v3' ? 'warning' : 'info', bordered: false, size: 'small' },
        { default: () => row.snmp_version },
      ),
  },
  { title: '端口', key: 'port', width: 80 },
  {
    title: '删除时间',
    key: 'updated_at',
    width: 180,
    render: (row) => formatDateTime(row.updated_at),
  },
]

const loadRecycleBinData = async (params: {
  page?: number
  page_size?: number
  keyword?: string
}) => {
  const res = await getRecycleBinSnmpCredentials(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleRestore = async (row: DeptSnmpCredential) => {
  try {
    await restoreSnmpCredential(row.id)
    $alert.success('SNMP 凭据已恢复')
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // ignore
  }
}

const handleBatchRestore = async (ids: Array<string | number>) => {
  try {
    const res = await batchRestoreSnmpCredentials(ids.map(String))
    $alert.success(`成功恢复 ${res.data.success_count} 条 SNMP 凭据`)
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // ignore
  }
}

const handleHardDelete = async (row: DeptSnmpCredential) => {
  try {
    await hardDeleteSnmpCredential(row.id)
    $alert.success('SNMP 凭据已彻底删除')
    recycleBinRef.value?.reload()
  } catch {
    // ignore
  }
}

const handleBatchHardDelete = async (ids: Array<string | number>) => {
  try {
    const res = await batchHardDeleteSnmpCredentials(ids.map(String))
    $alert.success(`成功彻底删除 ${res.data.success_count} 条 SNMP 凭据`)
    recycleBinRef.value?.reload()
  } catch {
    // ignore
  }
}

interface TreeSelectOption {
  label: string
  key: string
  children?: TreeSelectOption[]
}

const deptTreeOptions = ref<TreeSelectOption[]>([])
const deptFlatOptions = ref<Array<{ label: string; value: string }>>([])

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
    const tree = transform(res.data || [])
    deptTreeOptions.value = tree

    const flat: Array<{ label: string; value: string }> = []
    const walk = (items: TreeSelectOption[], prefix = '') => {
      for (const it of items) {
        const label = prefix ? `${prefix} / ${it.label}` : it.label
        flat.push({ label, value: it.key })
        if (it.children && it.children.length) walk(it.children, label)
      }
    }
    walk(tree)
    deptFlatOptions.value = flat
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchDeptTree()
})

const snmpVersionOptions = [
  { label: 'v2c', value: 'v2c' },
  { label: 'v3', value: 'v3' },
]

const columns: DataTableColumns<DeptSnmpCredential> = [
  { type: 'selection', fixed: 'left' },
  {
    title: '所属部门',
    key: 'dept_name',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.dept_name || '-',
  },
  {
    title: 'SNMP 版本',
    key: 'snmp_version',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { type: row.snmp_version === 'v3' ? 'warning' : 'info', bordered: false, size: 'small' },
        { default: () => row.snmp_version },
      ),
  },
  { title: '端口', key: 'port', width: 80 },
  {
    title: '团体字串',
    key: 'has_community',
    width: 110,
    render: (row) =>
      row.snmp_version === 'v2c'
        ? h(
            NTag,
            { type: row.has_community ? 'success' : 'default', bordered: false, size: 'small' },
            { default: () => (row.has_community ? '已配置' : '未配置') },
          )
        : '-',
  },
  {
    title: '描述',
    key: 'description',
    width: 220,
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

const searchFilters = computed<FilterConfig[]>(() => [
  { key: 'dept_id', placeholder: '部门筛选', options: deptFlatOptions.value, width: 220 },
])

const loadData = async (params: SnmpCredentialSearchParams) => {
  const res = await getSnmpCredentials(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: DeptSnmpCredential) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
}

// ==================== 批量删除 ====================

const handleBatchDelete = (ids: Array<string | number>) => {
  if (ids.length === 0) {
    $alert.warning('请先选择要删除的 SNMP 凭据')
    return
  }
  dialog.warning({
    title: '确认批量删除',
    content: `确定要删除选中的 ${ids.length} 条 SNMP 凭据吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteSnmpCredentials(ids.map(String))
        $alert.success(`成功删除 ${res.data.success_count} 条 SNMP 凭据`)
        selectedRowKeys.value = []
        tableRef.value?.reload()
      } catch {
        // ignore
      }
    },
  })
}

const handleRecycleBin = () => {
  showRecycleBin.value = true
  recycleBinRef.value?.reload()
}

const modalType = ref<'create' | 'edit'>('create')
const showModal = ref(false)
const formRef = ref()
const model = reactive({
  id: '',
  dept_id: '' as string,
  snmp_version: 'v2c' as SnmpVersion,
  port: 161,
  community: '',
  v3_username: '',
  v3_auth_key: '',
  v3_priv_key: '',
  v3_auth_proto: '',
  v3_priv_proto: '',
  v3_security_level: '',
  description: '',
})

const rules: FormRules = {
  dept_id: { required: true, message: '请选择部门', trigger: 'change' },
  snmp_version: { required: true, message: '请选择 SNMP 版本', trigger: 'change' },
  port: { required: true, type: 'number', message: '请输入端口', trigger: ['input', 'blur'] },
}

const handleCreate = () => {
  modalType.value = 'create'
  Object.assign(model, {
    id: '',
    dept_id: '',
    snmp_version: 'v2c',
    port: 161,
    community: '',
    v3_username: '',
    v3_auth_key: '',
    v3_priv_key: '',
    v3_auth_proto: '',
    v3_priv_proto: '',
    v3_security_level: '',
    description: '',
  })
  fetchDeptTree()
  showModal.value = true
}

const handleEdit = (row: DeptSnmpCredential) => {
  modalType.value = 'edit'
  Object.assign(model, {
    id: row.id,
    dept_id: row.dept_id,
    snmp_version: row.snmp_version,
    port: row.port,
    community: '',
    v3_username: '',
    v3_auth_key: '',
    v3_priv_key: '',
    v3_auth_proto: '',
    v3_priv_proto: '',
    v3_security_level: '',
    description: row.description || '',
  })
  fetchDeptTree()
  showModal.value = true
}

const submit = async (e: MouseEvent) => {
  e.preventDefault()
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  try {
    const isV2c = model.snmp_version === 'v2c'
    const isV3 = model.snmp_version === 'v3'

    if (modalType.value === 'create') {
      await createSnmpCredential({
        dept_id: model.dept_id,
        snmp_version: model.snmp_version,
        port: model.port,
        community: isV2c && model.community ? model.community : undefined,
        v3_username: isV3 && model.v3_username ? model.v3_username : undefined,
        v3_auth_key: isV3 && model.v3_auth_key ? model.v3_auth_key : undefined,
        v3_priv_key: isV3 && model.v3_priv_key ? model.v3_priv_key : undefined,
        v3_auth_proto: isV3 && model.v3_auth_proto ? model.v3_auth_proto : undefined,
        v3_priv_proto: isV3 && model.v3_priv_proto ? model.v3_priv_proto : undefined,
        v3_security_level: isV3 && model.v3_security_level ? model.v3_security_level : undefined,
        description: model.description || undefined,
      })
      $alert.success('SNMP 凭据创建成功')
    } else {
      await updateSnmpCredential(model.id, {
        snmp_version: model.snmp_version,
        port: model.port,
        community: isV2c && model.community ? model.community : undefined,
        v3_username: isV3 && model.v3_username ? model.v3_username : undefined,
        v3_auth_key: isV3 && model.v3_auth_key ? model.v3_auth_key : undefined,
        v3_priv_key: isV3 && model.v3_priv_key ? model.v3_priv_key : undefined,
        v3_auth_proto: isV3 && model.v3_auth_proto ? model.v3_auth_proto : undefined,
        v3_priv_proto: isV3 && model.v3_priv_proto ? model.v3_priv_proto : undefined,
        v3_security_level: isV3 && model.v3_security_level ? model.v3_security_level : undefined,
        description: model.description || undefined,
      })
      $alert.success('SNMP 凭据更新成功')
    }

    showModal.value = false
    tableRef.value?.reload()
  } catch {
    // ignore
  }
}

const handleDelete = (row: DeptSnmpCredential) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除该 SNMP 凭据吗？（部门: ${row.dept_name || row.dept_id}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteSnmpCredential(row.id)
        $alert.success('SNMP 凭据已删除')
        tableRef.value?.reload()
      } catch {
        // ignore
      }
    },
  })
}
</script>

<template>
  <div class="snmp-credentials p-4">
    <ProTable
      ref="tableRef"
      title="SNMP 凭据"
      :columns="columns"
      :request="loadData"
      :row-key="(row: DeptSnmpCredential) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索部门/描述"
      :search-filters="searchFilters"
      v-model:checked-row-keys="selectedRowKeys"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-batch-delete
      show-recycle-bin
      :scroll-x="1100"
    />

    <!-- 回收站 Modal -->
    <RecycleBinModal
      ref="recycleBinRef"
      v-model:show="showRecycleBin"
      title="回收站 (已删除 SNMP 凭据)"
      :columns="recycleBinColumns"
      :request="loadRecycleBinData"
      :row-key="(row: DeptSnmpCredential) => row.id"
      search-placeholder="搜索部门/描述..."
      :scroll-x="700"
      @restore="handleRestore"
      @batch-restore="handleBatchRestore"
      @hard-delete="handleHardDelete"
      @batch-hard-delete="handleBatchHardDelete"
    />

    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="modalType === 'create' ? '新建 SNMP 凭据' : '编辑 SNMP 凭据'"
      style="width: 520px"
    >
      <n-form ref="formRef" :model="model" :rules="rules" label-placement="left" label-width="120">
        <n-form-item label="所属部门" path="dept_id">
          <n-tree-select
            v-model:value="model.dept_id"
            :options="deptTreeOptions"
            placeholder="请选择部门"
            :disabled="modalType === 'edit'"
            key-field="key"
            label-field="label"
          />
        </n-form-item>

        <n-form-item label="SNMP 版本" path="snmp_version">
          <n-select v-model:value="model.snmp_version" :options="snmpVersionOptions" />
        </n-form-item>

        <n-form-item label="端口" path="port">
          <n-input-number
            v-model:value="model.port"
            :min="1"
            :max="65535"
            :update-value-on-input="true"
            placeholder="161"
            style="width: 100%"
          />
        </n-form-item>

        <n-form-item v-if="model.snmp_version === 'v2c'" label="Community">
          <n-input
            v-model:value="model.community"
            type="password"
            show-password-on="click"
            :placeholder="
              modalType === 'edit' ? '留空则保持不变；填空字符串将清空' : '请输入 community'
            "
          />
        </n-form-item>

        <template v-if="model.snmp_version === 'v3'">
          <n-form-item label="v3 用户名">
            <n-input v-model:value="model.v3_username" placeholder="用户名" />
          </n-form-item>
          <n-form-item label="v3 Auth Key">
            <n-input
              v-model:value="model.v3_auth_key"
              type="password"
              show-password-on="click"
              placeholder="Auth Key（留空则保持不变）"
            />
          </n-form-item>
          <n-form-item label="v3 Priv Key">
            <n-input
              v-model:value="model.v3_priv_key"
              type="password"
              show-password-on="click"
              placeholder="Priv Key（留空则保持不变）"
            />
          </n-form-item>
          <n-form-item label="v3 Auth 协议">
            <n-input v-model:value="model.v3_auth_proto" placeholder="例如: SHA" />
          </n-form-item>
          <n-form-item label="v3 Priv 协议">
            <n-input v-model:value="model.v3_priv_proto" placeholder="例如: AES" />
          </n-form-item>
          <n-form-item label="v3 安全级别">
            <n-input v-model:value="model.v3_security_level" placeholder="例如: authPriv" />
          </n-form-item>
        </template>

        <n-form-item label="描述">
          <n-input v-model:value="model.description" type="textarea" :rows="2" placeholder="描述" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" @click="submit">提交</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.snmp-credentials {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
