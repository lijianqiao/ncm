<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  NSelect,
  NPopover,
  NIcon,
  useDialog,
  type DataTableColumns,
  NTag,
  NSpace,
  NCode,
  type DropdownOption,
} from 'naive-ui'
import { HelpCircleOutline } from '@vicons/ionicons5'
import { $alert } from '@/utils/alert'
import {
  getTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  createTemplateVersion,
  submitTemplate,
  approveTemplate,
  batchDeleteTemplates,
  getRecycleBinTemplates,
  restoreTemplate,
  batchRestoreTemplates,
  hardDeleteTemplate,
  batchHardDeleteTemplates,
  type Template,
  type TemplateSearchParams,
  type TemplateType,
  type TemplateStatus,
  type DeviceType,
} from '@/api/templates'
import { getUsers } from '@/api/users'
import { getDeviceOptions, type Device, type DeviceVendor } from '@/api/devices'
import { renderTemplate } from '@/api/render'
import { formatDateTime } from '@/utils/date'
import { formatUserDisplayNameParts } from '@/utils/user'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'

defineOptions({
  name: 'TemplateManagement',
})

const dialog = useDialog()
const tableRef = ref()
const selectedRowKeys = ref<string[]>()

// ==================== 回收站 ====================

const showRecycleBin = ref(false)
const recycleBinRef = ref()

const recycleBinColumns: DataTableColumns<Template> = [
  { type: 'selection', fixed: 'left' },
  { title: '模板名称', key: 'name', width: 200, ellipsis: { tooltip: true } },
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
  { title: '版本', key: 'version', width: 80 },
  {
    title: '删除时间',
    key: 'updated_at',
    width: 180,
    render: (row) => (row.updated_at ? formatDateTime(row.updated_at) : '-'),
  },
]

const loadRecycleBinData = async (params: {
  page?: number
  page_size?: number
  keyword?: string
}) => {
  const res = await getRecycleBinTemplates(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

const handleRestore = async (row: Template) => {
  try {
    await restoreTemplate(row.id)
    $alert.success('模板已恢复')
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleBatchRestore = async (ids: Array<string | number>) => {
  try {
    const res = await batchRestoreTemplates(ids.map(String))
    $alert.success(`成功恢复 ${res.data.success_count} 个模板`)
    recycleBinRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleHardDelete = async (row: Template) => {
  try {
    await hardDeleteTemplate(row.id)
    $alert.success('模板已彻底删除')
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleBatchHardDelete = async (ids: Array<string | number>) => {
  try {
    const res = await batchHardDeleteTemplates(ids.map(String))
    $alert.success(`成功彻底删除 ${res.data.success_count} 个模板`)
    recycleBinRef.value?.reload()
  } catch {
    // Error handled
  }
}

const templateContentExample = `# 1) 直接使用 params

# 创建 VLAN
vlan {{ params.vlan_id }}
 name {{ params.vlan_name }}

# 2) 可选字段写法（避免缺参）
{% if params.get('desc') %}
 description {{ params.get('desc') }}
{% endif %}

# 3) 设备上下文（预览时可选 device_id 注入）
{% if device %}
# device: {{ device.name }} ({{ device.ip_address }})
{% endif %}

# 4) 按厂商分支
{% if device and device.vendor == 'h3c' %}
# H3C 命令...
{% elif device and device.vendor == 'huawei' %}
# Huawei 命令...
{% elif device and device.vendor == 'cisco' %}
# Cisco 命令...
{% else %}
# other/unknown
{% endif %}`

const templateParametersSchemaExample = `{
  "type": "object",
  "properties": {
    "vlan_id": { "type": "integer", "minimum": 1, "maximum": 4094 },
    "vlan_name": { "type": "string", "minLength": 1 }
  },
  "required": ["vlan_id", "vlan_name"],
  "additionalProperties": false
}`

// ==================== 常量定义 ====================

const vendorOptions = [
  { label: 'Cisco', value: 'cisco' },
  { label: 'Huawei', value: 'huawei' },
  { label: 'H3C', value: 'h3c' },
  { label: '其他', value: 'other' },
]

const templateTypeOptions = [
  { label: 'VLAN配置', value: 'vlan' },
  { label: '接口配置', value: 'interface' },
  { label: 'ACL策略', value: 'acl' },
  { label: '路由配置', value: 'route' },
  { label: 'QoS策略', value: 'qos' },
  { label: '自定义', value: 'custom' },
]

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '待审批', value: 'pending' },
  { label: '已批准', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
  { label: '已废弃', value: 'deprecated' },
]

const deviceTypeOptions = [
  { label: '交换机', value: 'switch' },
  { label: '路由器', value: 'router' },
  { label: '防火墙', value: 'firewall' },
  { label: '全部', value: 'all' },
]

const templateTypeLabelMap: Record<TemplateType, string> = {
  vlan: 'VLAN配置',
  interface: '接口配置',
  acl: 'ACL策略',
  route: '路由配置',
  qos: 'QoS策略',
  custom: '自定义',
}

const statusLabelMap: Record<TemplateStatus, string> = {
  draft: '草稿',
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  deprecated: '已废弃',
}

const statusColorMap: Record<TemplateStatus, 'default' | 'info' | 'success' | 'warning' | 'error'> =
  {
    draft: 'default',
    pending: 'info',
    approved: 'success',
    rejected: 'error',
    deprecated: 'warning',
  }

const vendorLabelMap: Record<DeviceVendor, string> = {
  cisco: 'Cisco',
  huawei: 'Huawei',
  h3c: 'H3C',
  other: '其他',
}

const deviceTypeLabelMap: Record<DeviceType, string> = {
  switch: '交换机',
  router: '路由器',
  firewall: '防火墙',
  all: '全部',
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<Template> = [
  { type: 'selection', fixed: 'left' },
  { title: '模板名称', key: 'name', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
  {
    title: '描述',
    key: 'description',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.description || '-',
  },
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
    title: '设备类型',
    key: 'device_type',
    width: 100,
    render: (row) => (row.device_type ? deviceTypeLabelMap[row.device_type] : '-'),
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
    width: 180,
    render: (row) => row.created_by_name || '-',
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
    render: (row) => (row.updated_at ? formatDateTime(row.updated_at) : '-'),
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
  { label: '预览渲染', key: 'render_preview' },
  { label: '编辑', key: 'edit' },
  { label: '新建版本', key: 'new_version' },
  { label: '提交审批', key: 'submit' },
  { label: '审批', key: 'approve' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Template) => {
  if (key === 'view') handleView(row)
  if (key === 'render_preview') handleRenderPreview(row)
  if (key === 'edit') handleEdit(row)
  if (key === 'new_version') handleNewVersion(row)
  if (key === 'submit') handleSubmit(row)
  if (key === 'approve') handleApprove(row)
  if (key === 'delete') handleDelete(row)
}

// ==================== 批量删除 ====================

const handleBatchDelete = (ids: Array<string | number>) => {
  if (ids.length === 0) {
    $alert.warning('请先选择要删除的模板')
    return
  }
  dialog.warning({
    title: '确认批量删除',
    content: `确定要删除选中的 ${ids.length} 个模板吗？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await batchDeleteTemplates(ids.map(String))
        $alert.success(`成功删除 ${res.data.success_count} 个模板`)
        selectedRowKeys.value = []
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleRecycleBin = () => {
  showRecycleBin.value = true
  recycleBinRef.value?.reload()
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

// ==================== 渲染预览(Dry-Run) ====================

const showRenderModal = ref(false)
const renderTarget = ref<Template | null>(null)
const renderParamsText = ref<string>('{}')
const renderDeviceId = ref<string | null>(null)
const renderDeviceOptions = ref<Array<{ label: string; value: string }>>([])
const renderDeviceLoading = ref(false)
const renderLoading = ref(false)
const renderResult = ref<string>('')

const loadRenderDevices = async () => {
  if (renderDeviceLoading.value) return
  if (renderDeviceOptions.value.length > 0) return

  renderDeviceLoading.value = true
  try {
    const res = await getDeviceOptions()
    renderDeviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
  } catch {
    // 忽略：设备列表加载失败不影响手动选择
  } finally {
    renderDeviceLoading.value = false
  }
}

const handleRenderPreview = async (row: Template) => {
  renderTarget.value = row
  renderResult.value = ''
  renderDeviceId.value = null
  showRenderModal.value = true
  await loadRenderDevices()
}

const submitRenderPreview = async () => {
  if (!renderTarget.value) return

  let params: Record<string, unknown> = {}
  const raw = (renderParamsText.value || '').trim()
  if (raw) {
    try {
      params = JSON.parse(raw)
    } catch {
      $alert.warning('模板参数(JSON)格式错误')
      return
    }
  }

  renderLoading.value = true
  try {
    const res = await renderTemplate(renderTarget.value.id, {
      params,
      device_id: renderDeviceId.value || undefined,
    })
    renderResult.value = res.data.rendered
  } catch {
    // Error handled
  } finally {
    renderLoading.value = false
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
  template_type: 'custom' as TemplateType,
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
    template_type: 'custom',
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

const showSubmitModal = ref(false)
const submitLoading = ref(false)
const submitTarget = ref<Template | null>(null)
const submitComment = ref('')
const submitApproverIds = ref<string[]>([])

const submitApproverOptions = ref<Array<{ label: string; value: string }>>([])
const submitApproverLoading = ref(false)

const loadSubmitApprovers = async () => {
  submitApproverLoading.value = true
  try {
    const res = await getUsers({ page: 1, page_size: 200 })
    submitApproverOptions.value = (res.data.items || []).map((u) => {
      const nickname = (u.nickname || '').trim()
      const username = (u.username || '').trim()
      const label = formatUserDisplayNameParts(nickname, username, u.id)
      return { label, value: u.id }
    })
  } catch {
    submitApproverOptions.value = []
  } finally {
    submitApproverLoading.value = false
  }
}

const handleSubmit = (row: Template) => {
  // 说明：提交后会进入 pending，后续动作应该是“审批”，不是再次提交。
  if (row.status === 'pending') {
    void handleApprove(row)
    return
  }

  if (row.status !== 'draft' && row.status !== 'rejected') {
    $alert.warning('当前状态不可提交审批')
    return
  }
  submitTarget.value = row
  submitComment.value = ''
  submitApproverIds.value = []
  showSubmitModal.value = true
  void loadSubmitApprovers()
}

const submitApproval = async () => {
  if (!submitTarget.value) return

  if (submitApproverIds.value.length > 0 && submitApproverIds.value.length !== 3) {
    $alert.warning('审批人需选择 3 个（或不选）')
    return
  }

  submitLoading.value = true
  try {
    await submitTemplate(submitTarget.value.id, {
      comment: submitComment.value || undefined,
      approver_ids: submitApproverIds.value.length > 0 ? submitApproverIds.value : undefined,
    })
    $alert.success('模板已提交审批')
    showSubmitModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  } finally {
    submitLoading.value = false
  }
}

// ==================== 审批（通过/拒绝） ====================

const showApproveModal = ref(false)
const approveLoading = ref(false)
const approveTarget = ref<Template | null>(null)
const approveLevel = ref<number | null>(null)
const approveDecision = ref<'approve' | 'reject'>('approve')
const approveComment = ref('')

const _inferNextApprovalLevel = (tpl: Template): number | null => {
  const steps = tpl.approvals || []
  const pending = steps.filter((s) => s.status === 'pending').sort((a, b) => a.level - b.level)

  if (pending.length === 0) return null
  const first = pending[0]
  return first ? first.level : null
}

const handleApprove = async (row: Template) => {
  if (row.status !== 'pending') {
    $alert.warning('只有待审批的模板才能审批')
    return
  }

  approveLoading.value = true
  try {
    const res = await getTemplate(row.id)
    approveTarget.value = res.data
    approveLevel.value = _inferNextApprovalLevel(res.data)
    approveDecision.value = 'approve'
    approveComment.value = ''
    showApproveModal.value = true

    if (!approveLevel.value) {
      $alert.warning('未找到待审批步骤，可能已完成审批')
    }
  } catch {
    // Error handled
  } finally {
    approveLoading.value = false
  }
}

const submitApprove = async () => {
  if (!approveTarget.value) return
  if (!approveLevel.value) {
    $alert.warning('未找到待审批级别')
    return
  }

  approveLoading.value = true
  try {
    await approveTemplate(approveTarget.value.id, {
      level: approveLevel.value,
      approve: approveDecision.value === 'approve',
      comment: approveComment.value || undefined,
    })
    $alert.success('审批已提交')
    showApproveModal.value = false
    tableRef.value?.reload()

    // 若详情弹窗打开，顺便刷新一次详情
    if (showViewModal.value && viewData.value && viewData.value.id === approveTarget.value.id) {
      const res = await getTemplate(approveTarget.value.id)
      viewData.value = res.data
    }
  } catch {
    // Error handled
  } finally {
    approveLoading.value = false
  }
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
      v-model:checked-row-keys="selectedRowKeys"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-batch-delete
      show-recycle-bin
      :scroll-x="1200"
    />

    <!-- 回收站 Modal -->
    <RecycleBinModal
      ref="recycleBinRef"
      v-model:show="showRecycleBin"
      title="回收站 (已删除模板)"
      :columns="recycleBinColumns"
      :request="loadRecycleBinData"
      :row-key="(row: Template) => row.id"
      search-placeholder="搜索模板名称..."
      :scroll-x="900"
      @restore="handleRestore"
      @batch-restore="handleBatchRestore"
      @hard-delete="handleHardDelete"
      @batch-hard-delete="handleBatchHardDelete"
    />

    <!-- 提交审批 Modal -->
    <n-modal v-model:show="showSubmitModal" preset="card" title="提交审批" style="width: 520px">
      <n-space vertical style="width: 100%">
        <div v-if="submitTarget">
          <p>模板: {{ submitTarget.name }}</p>
          <p style="color: #666">说明：可不指定审批人；或选择 3 个审批人</p>
        </div>
        <n-form label-placement="left" label-width="110" style="width: 100%">
          <n-form-item label="审批人(可选)">
            <n-select
              v-model:value="submitApproverIds"
              multiple
              :options="submitApproverOptions"
              :loading="submitApproverLoading"
              placeholder="不选=允许有权限者审批；选=指定 3 人"
            />
          </n-form-item>
          <n-form-item label="提交备注">
            <n-input v-model:value="submitComment" type="textarea" :rows="2" placeholder="可选" />
          </n-form-item>
        </n-form>
        <n-space justify="end">
          <n-button @click="showSubmitModal = false">取消</n-button>
          <n-button type="primary" :loading="submitLoading" @click="submitApproval"
            >确认提交</n-button
          >
        </n-space>
      </n-space>
    </n-modal>

    <!-- 审批 Modal -->
    <n-modal v-model:show="showApproveModal" preset="card" title="审批" style="width: 520px">
      <n-space vertical style="width: 100%">
        <div v-if="approveTarget">
          <p>模板: {{ approveTarget.name }}</p>
          <p style="color: #666">当前审批级别: 第 {{ approveLevel || '-' }} 级</p>
        </div>
        <n-form label-placement="left" label-width="110" style="width: 100%">
          <n-form-item label="审批动作">
            <n-select
              v-model:value="approveDecision"
              :options="[
                { label: '通过', value: 'approve' },
                { label: '拒绝', value: 'reject' },
              ]"
            />
          </n-form-item>
          <n-form-item label="审批意见">
            <n-input v-model:value="approveComment" type="textarea" :rows="2" placeholder="可选" />
          </n-form-item>
        </n-form>
        <n-space justify="end">
          <n-button @click="showApproveModal = false">取消</n-button>
          <n-button type="primary" :loading="approveLoading" @click="submitApprove">确认</n-button>
        </n-space>
      </n-space>
    </n-modal>

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
          <div v-if="viewData.approvals && viewData.approvals.length > 0">
            <strong>审批流程:</strong>
            <n-space vertical style="margin-top: 8px">
              <div v-for="a in viewData.approvals" :key="a.level">
                <n-tag
                  :type="
                    a.status === 'approved'
                      ? 'success'
                      : a.status === 'rejected'
                        ? 'error'
                        : 'default'
                  "
                  size="small"
                  style="margin-right: 8px"
                >
                  第 {{ a.level }} 级
                </n-tag>
                <span>审批人: {{ a.approver_name || '待指定' }}</span>
                <span style="margin-left: 12px">
                  状态:
                  {{
                    a.status === 'approved'
                      ? '已批准'
                      : a.status === 'rejected'
                        ? '已拒绝'
                        : '待审批'
                  }}
                </span>
                <span v-if="a.approved_at" style="margin-left: 12px"
                  >时间: {{ formatDateTime(a.approved_at) }}</span
                >
                <div v-if="a.comment" style="color: #666; margin-top: 4px">
                  备注: {{ a.comment }}
                </div>
              </div>
            </n-space>
          </div>
          <div><strong>描述:</strong> {{ viewData.description || '-' }}</div>
          <div>
            <strong>模板内容:</strong>
            <n-code
              :code="viewData.content"
              language="jinja2"
              style="max-height: 400px; overflow: auto"
            />
          </div>
          <div v-if="viewData.parameters">
            <strong>参数定义:</strong>
            <n-code
              :code="viewData.parameters"
              language="json"
              style="max-height: 200px; overflow: auto"
            />
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
          <n-select v-model:value="createModel.template_type" :options="templateTypeOptions" />
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
        <n-form-item path="content">
          <template #label>
            <span style="display: inline-flex; align-items: center; gap: 6px">
              <span>模板内容</span>
              <n-popover
                trigger="click"
                placement="right-start"
                :width="480"
                :content-style="{ maxHeight: '320px', overflow: 'auto' }"
              >
                <template #trigger>
                  <n-icon size="16" style="cursor: pointer; opacity: 0.75">
                    <HelpCircleOutline />
                  </n-icon>
                </template>
                <n-space vertical size="small">
                  <div style="font-weight: 600">使用示例</div>
                  <n-code
                    language="jinja2"
                    :code="templateContentExample"
                    style="max-height: 260px; overflow: auto"
                  />
                </n-space>
              </n-popover>
            </span>
          </template>
          <n-input
            v-model:value="createModel.content"
            type="textarea"
            placeholder="Jinja2 模板内容"
            :rows="10"
            style="font-family: monospace"
          />
        </n-form-item>
        <n-form-item>
          <template #label>
            <span style="display: inline-flex; align-items: center; gap: 6px">
              <span>参数定义</span>
              <n-popover
                trigger="click"
                placement="right-start"
                :width="480"
                :content-style="{ maxHeight: '320px', overflow: 'auto' }"
              >
                <template #trigger>
                  <n-icon size="16" style="cursor: pointer; opacity: 0.75">
                    <HelpCircleOutline />
                  </n-icon>
                </template>
                <n-space vertical size="small">
                  <div style="font-weight: 600">JSON Schema 示例</div>
                  <div style="opacity: 0.8">
                    这里填写 JSON Schema（字符串），用于校验你在“渲染预览/配置下发”里传入的 params。
                  </div>
                  <n-code
                    language="json"
                    :code="templateParametersSchemaExample"
                    style="max-height: 220px; overflow: auto"
                  />
                </n-space>
              </n-popover>
            </span>
          </template>
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

    <!-- 渲染预览 Modal -->
    <n-modal
      v-model:show="showRenderModal"
      preset="card"
      title="模板渲染预览(Dry-Run)"
      style="width: 900px; max-height: 85vh; overflow: auto"
    >
      <n-space vertical size="large" style="width: 100%">
        <div v-if="renderTarget" style="font-weight: 600">
          模板：{{ renderTarget.name }}（v{{ renderTarget.version }}）
        </div>

        <n-form-item label="设备上下文(可选)">
          <n-select
            v-model:value="renderDeviceId"
            :options="renderDeviceOptions"
            placeholder="选择一个设备用于 device 上下文（可不选）"
            filterable
            clearable
            :loading="renderDeviceLoading"
          />
        </n-form-item>

        <n-form-item label="模板参数(JSON)">
          <n-input
            v-model:value="renderParamsText"
            type="textarea"
            placeholder='{"key": "value"}'
            :rows="6"
            style="font-family: monospace"
          />
        </n-form-item>

        <n-space justify="end">
          <n-button @click="showRenderModal = false">关闭</n-button>
          <n-button type="primary" :loading="renderLoading" @click="submitRenderPreview"
            >渲染预览</n-button
          >
        </n-space>

        <div v-if="renderResult">
          <div style="font-weight: 600; margin-bottom: 8px">渲染结果</div>
          <n-code :code="renderResult" language="text" style="max-height: 360px; overflow: auto" />
        </div>
      </n-space>
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
