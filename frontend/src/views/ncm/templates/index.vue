<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  NSelect,
  useDialog,
  type DataTableColumns,
  NTag,
  NSpace,
  NCode,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  createTemplateVersion,
  submitTemplate,
  type Template,
  type TemplateSearchParams,
  type TemplateType,
  type TemplateStatus,
  type DeviceType,
} from '@/api/templates'
import { type DeviceVendor } from '@/api/devices'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'TemplateManagement',
})

const dialog = useDialog()
const tableRef = ref()

// ==================== 常量定义 ====================

const vendorOptions = [
  { label: 'Cisco', value: 'cisco' },
  { label: 'Huawei', value: 'huawei' },
  { label: 'H3C', value: 'h3c' },
  { label: 'Ruijie', value: 'ruijie' },
  { label: '其他', value: 'other' },
]

const templateTypeOptions = [
  { label: '配置模板', value: 'config' },
  { label: '命令模板', value: 'command' },
  { label: '脚本模板', value: 'script' },
]

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '待审批', value: 'pending' },
  { label: '已批准', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
]

const deviceTypeOptions = [
  { label: '路由器', value: 'router' },
  { label: '交换机', value: 'switch' },
  { label: '防火墙', value: 'firewall' },
  { label: '无线', value: 'wireless' },
  { label: '服务器', value: 'server' },
  { label: '其他', value: 'other' },
]

const templateTypeLabelMap: Record<TemplateType, string> = {
  config: '配置模板',
  command: '命令模板',
  script: '脚本模板',
}

const statusLabelMap: Record<TemplateStatus, string> = {
  draft: '草稿',
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
}

const statusColorMap: Record<TemplateStatus, 'default' | 'info' | 'success' | 'error'> = {
  draft: 'default',
  pending: 'info',
  approved: 'success',
  rejected: 'error',
}

const vendorLabelMap: Record<DeviceVendor, string> = {
  cisco: 'Cisco',
  huawei: 'Huawei',
  h3c: 'H3C',
  ruijie: 'Ruijie',
  other: '其他',
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<Template> = [
  { type: 'selection', fixed: 'left' },
  { title: '模板名称', key: 'name', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'template_type',
    width: 100,
    render: (row) => templateTypeLabelMap[row.template_type],
  },
  {
    title: '适用厂商',
    key: 'vendors',
    width: 150,
    render: (row) => row.vendors.map((v) => vendorLabelMap[v]).join(', ') || '-',
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
  { title: '版本', key: 'version', width: 80 },
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
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'vendor', placeholder: '厂商', options: vendorOptions, width: 120 },
  { key: 'template_type', placeholder: '模板类型', options: templateTypeOptions, width: 120 },
  { key: 'status', placeholder: '状态', options: statusOptions, width: 100 },
]

// ==================== 数据加载 ====================

const loadData = async (params: TemplateSearchParams) => {
  const res = await getTemplates(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看', key: 'view' },
  { label: '编辑', key: 'edit' },
  { label: '新建版本', key: 'new_version' },
  { label: '提交审批', key: 'submit' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Template) => {
  if (key === 'view') handleView(row)
  if (key === 'edit') handleEdit(row)
  if (key === 'new_version') handleNewVersion(row)
  if (key === 'submit') handleSubmit(row)
  if (key === 'delete') handleDelete(row)
}

// ==================== 查看模板 ====================

const showViewModal = ref(false)
const viewData = ref<Template | null>(null)
const viewLoading = ref(false)

const handleView = async (row: Template) => {
  viewLoading.value = true
  showViewModal.value = true
  try {
    const res = await getTemplate(row.id)
    viewData.value = res.data
  } catch {
    showViewModal.value = false
  } finally {
    viewLoading.value = false
  }
}

// ==================== 创建/编辑模板 ====================

const modalType = ref<'create' | 'edit'>('create')
const showCreateModal = ref(false)
const createFormRef = ref()
const createModel = ref({
  id: '',
  name: '',
  description: '',
  template_type: 'config' as TemplateType,
  content: '',
  vendors: [] as DeviceVendor[],
  device_type: null as DeviceType | null,
  parameters: '',
})

const createRules = {
  name: { required: true, message: '请输入模板名称', trigger: 'blur' },
  content: { required: true, message: '请输入模板内容', trigger: 'blur' },
  vendors: { required: true, message: '请选择适用厂商', trigger: 'change', type: 'array' },
}

const handleCreate = () => {
  modalType.value = 'create'
  createModel.value = {
    id: '',
    name: '',
    description: '',
    template_type: 'config',
    content: '',
    vendors: [],
    device_type: null,
    parameters: '',
  }
  showCreateModal.value = true
}

const handleEdit = (row: Template) => {
  if (row.status !== 'draft' && row.status !== 'rejected') {
    $alert.warning('只能编辑草稿或已拒绝的模板')
    return
  }
  modalType.value = 'edit'
  createModel.value = {
    id: row.id,
    name: row.name,
    description: row.description || '',
    template_type: row.template_type,
    content: row.content,
    vendors: row.vendors,
    device_type: row.device_type,
    parameters: row.parameters || '',
  }
  showCreateModal.value = true
}

const submitCreate = (e: MouseEvent) => {
  e.preventDefault()
  createFormRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        const data = {
          name: createModel.value.name,
          description: createModel.value.description || undefined,
          template_type: createModel.value.template_type,
          content: createModel.value.content,
          vendors: createModel.value.vendors,
          device_type: createModel.value.device_type || undefined,
          parameters: createModel.value.parameters || undefined,
        }
        if (modalType.value === 'create') {
          await createTemplate(data)
          $alert.success('模板创建成功')
        } else {
          await updateTemplate(createModel.value.id, data)
          $alert.success('模板更新成功')
        }
        showCreateModal.value = false
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    }
  })
}

// ==================== 删除模板 ====================

const handleDelete = (row: Template) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除模板 "${row.name}" 吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteTemplate(row.id)
        $alert.success('模板已删除')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 新建版本 ====================

const handleNewVersion = (row: Template) => {
  if (row.status !== 'approved') {
    $alert.warning('只能基于已批准的模板创建新版本')
    return
  }
  dialog.info({
    title: '新建版本',
    content: `确定要基于模板 "${row.name}" 创建新版本吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await createTemplateVersion(row.id)
        $alert.success('新版本创建成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 提交审批 ====================

const handleSubmit = (row: Template) => {
  if (row.status !== 'draft' && row.status !== 'rejected') {
    $alert.warning('只能提交草稿或已拒绝的模板')
    return
  }
  dialog.info({
    title: '提交审批',
    content: `确定要提交模板 "${row.name}" 进行审批吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await submitTemplate(row.id)
        $alert.success('模板已提交审批')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}
</script>

<template>
  <div class="template-management p-4">
    <ProTable
      ref="tableRef"
      title="模板列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Template) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索模板名称/描述"
      :search-filters="searchFilters"
      @add="handleCreate"
      @context-menu-select="handleContextMenuSelect"
      show-add
      :scroll-x="1200"
    />

    <!-- 查看模板 Modal -->
    <n-modal
      v-model:show="showViewModal"
      preset="card"
      title="模板详情"
      style="width: 900px; max-height: 80vh"
    >
      <div v-if="viewLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="viewData">
        <n-space vertical>
          <n-space>
            <span><strong>名称:</strong> {{ viewData.name }}</span>
            <n-tag :type="statusColorMap[viewData.status]" size="small">
              {{ statusLabelMap[viewData.status] }}
            </n-tag>
            <span>版本: v{{ viewData.version }}</span>
          </n-space>
          <div>
            <strong>适用厂商:</strong>
            {{ viewData.vendors.map((v) => vendorLabelMap[v]).join(', ') }}
          </div>
          <div><strong>描述:</strong> {{ viewData.description || '-' }}</div>
          <div>
            <strong>模板内容:</strong>
            <n-code :code="viewData.content" language="jinja2" style="max-height: 400px; overflow: auto" />
          </div>
          <div v-if="viewData.parameters">
            <strong>参数定义:</strong>
            <n-code :code="viewData.parameters" language="json" style="max-height: 200px; overflow: auto" />
          </div>
        </n-space>
      </template>
    </n-modal>

    <!-- 创建/编辑模板 Modal -->
    <n-modal
      v-model:show="showCreateModal"
      preset="dialog"
      :title="modalType === 'create' ? '新建模板' : '编辑模板'"
      style="width: 800px"
    >
      <n-form
        ref="createFormRef"
        :model="createModel"
        :rules="createRules"
        label-placement="left"
        label-width="100"
      >
        <n-form-item label="模板名称" path="name">
          <n-input v-model:value="createModel.name" placeholder="请输入模板名称" />
        </n-form-item>
        <n-form-item label="模板类型">
          <n-select
            v-model:value="createModel.template_type"
            :options="templateTypeOptions"
          />
        </n-form-item>
        <n-form-item label="适用厂商" path="vendors">
          <n-select
            v-model:value="createModel.vendors"
            :options="vendorOptions"
            multiple
            placeholder="请选择适用厂商"
          />
        </n-form-item>
        <n-form-item label="设备类型">
          <n-select
            v-model:value="createModel.device_type"
            :options="deviceTypeOptions"
            placeholder="请选择设备类型（可选）"
            clearable
          />
        </n-form-item>
        <n-form-item label="描述">
          <n-input
            v-model:value="createModel.description"
            type="textarea"
            placeholder="模板描述"
            :rows="2"
          />
        </n-form-item>
        <n-form-item label="模板内容" path="content">
          <n-input
            v-model:value="createModel.content"
            type="textarea"
            placeholder="Jinja2 模板内容"
            :rows="10"
            style="font-family: monospace"
          />
        </n-form-item>
        <n-form-item label="参数定义">
          <n-input
            v-model:value="createModel.parameters"
            type="textarea"
            placeholder="JSON Schema 格式的参数定义（可选）"
            :rows="4"
            style="font-family: monospace"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showCreateModal = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">提交</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.template-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
