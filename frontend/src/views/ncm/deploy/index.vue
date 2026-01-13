<script setup lang="ts">
import { ref, h, computed } from 'vue'
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
  NDescriptions,
  NDescriptionsItem,
  NTimeline,
  NTimelineItem,
  NCode,
  NTable,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getDeployTasks,
  getDeployTask,
  createDeployTask,
  approveDeployTask,
  executeDeployTask,
  rollbackDeployTask,
  type DeployTask,
  type DeploySearchParams,
  type DeployTaskStatus,
  type DeviceDeployResult,
} from '@/api/deploy'
import { cacheOTP } from '@/api/credentials'
import { getTemplates, type Template } from '@/api/templates'
import { getDevices, type Device } from '@/api/devices'
import { getUsers, type User } from '@/api/users'
import { formatDateTime } from '@/utils/date'
import { formatUserDisplayName } from '@/utils/user'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'
import OtpModal from '@/components/common/OtpModal.vue'
import type { DeviceGroupType } from '@/types/enums'

/** OTP 所需分组信息 */
interface OtpRequiredGroup {
  dept_id: string
  device_group: DeviceGroupType
}

defineOptions({
  name: 'DeployManagement',
})

const dialog = useDialog()
const tableRef = ref()

// ==================== 常量定义 ====================

const statusOptions = [
  { label: '待审批', value: 'pending' },
  { label: '审批中', value: 'approving' },
  { label: '已批准', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
  { label: '执行中', value: 'running' },
  { label: '执行中', value: 'executing' },
  { label: '成功', value: 'success' },
  { label: '部分成功', value: 'partial' },
  { label: '失败', value: 'failed' },
  { label: '已暂停', value: 'paused' },
  { label: '已取消', value: 'cancelled' },
  { label: '已回滚', value: 'rollback' },
]

const statusLabelMap: Record<DeployTaskStatus, string> = {
  pending: '待审批',
  approving: '审批中',
  approved: '已批准',
  rejected: '已拒绝',
  running: '执行中',
  executing: '执行中',
  success: '成功',
  failed: '失败',
  partial: '部分成功',
  paused: '已暂停',
  cancelled: '已取消',
  rollback: '已回滚',
}

const statusColorMap: Record<
  DeployTaskStatus,
  'default' | 'info' | 'success' | 'error' | 'warning'
> = {
  pending: 'default',
  approving: 'info',
  approved: 'info',
  rejected: 'error',
  running: 'warning',
  executing: 'warning',
  success: 'success',
  failed: 'error',
  partial: 'warning',
  paused: 'warning',
  cancelled: 'default',
  rollback: 'warning',
}

const approvalStatusLabelMap: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
}

const approvalStatusColorMap: Record<string, 'default' | 'info' | 'success' | 'error' | 'warning'> =
  {
    pending: 'default',
    approved: 'success',
    rejected: 'error',
  }

const getTaskDeviceIds = (row: DeployTask): string[] => {
  return row.target_devices?.device_ids || row.device_ids || []
}

const getTaskDeviceCount = (row: DeployTask): number => {
  if (typeof row.total_devices === 'number') return row.total_devices
  return getTaskDeviceIds(row).length
}

const formatJson = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

// ==================== 表格列定义 ====================

const columns: DataTableColumns<DeployTask> = [
  { type: 'selection', fixed: 'left' },
  { title: '任务名称', key: 'name', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
  {
    title: '模板',
    key: 'template_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.template_name || '-',
  },
  {
    title: '设备数',
    key: 'device_count',
    width: 80,
    render: (row) => getTaskDeviceCount(row),
  },
  {
    title: '审批状态',
    key: 'approval_status',
    width: 100,
    render: (row) => {
      const s = row.approval_status || '-'
      if (s === '-') return '-'
      return h(
        NTag,
        { type: approvalStatusColorMap[s] || 'info', bordered: false, size: 'small' },
        { default: () => approvalStatusLabelMap[s] || s },
      )
    },
  },
  {
    title: '审批进度',
    key: 'current_approval_level',
    width: 90,
    render: (row) => `${row.current_approval_level ?? 0}/3`,
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
  {
    title: '创建人',
    key: 'created_by_name',
    width: 100,
    render: (row) => row.created_by_name || '-',
  },
  {
    title: '成功/失败',
    key: 'result_count',
    width: 100,
    render: (row) => `${row.success_count ?? 0}/${row.failed_count ?? 0}`,
  },
  {
    title: '干跑',
    key: 'dry_run',
    width: 70,
    render: (row) => (row.deploy_plan?.dry_run ? '是' : '否'),
  },
  {
    title: '并发',
    key: 'concurrency',
    width: 70,
    render: (row) => row.deploy_plan?.concurrency ?? '-',
  },
  {
    title: '批次',
    key: 'batch_size',
    width: 70,
    render: (row) => row.deploy_plan?.batch_size ?? '-',
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
  { key: 'status', placeholder: '状态', options: statusOptions, width: 120 },
]

// ==================== 数据加载 ====================

const loadData = async (params: DeploySearchParams) => {
  const res = await getDeployTasks(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// ==================== 右键菜单 ====================

const contextMenuOptions: DropdownOption[] = [
  { label: '查看详情', key: 'view' },
  { label: '查看结果', key: 'result' },
  { label: '审批', key: 'approve' },
  { label: '执行', key: 'execute' },
  { label: '回滚', key: 'rollback' },
]

const handleContextMenuSelect = (key: string | number, row: DeployTask) => {
  if (key === 'view') handleView(row)
  if (key === 'result') handleResult(row)
  if (key === 'approve') handleApprove(row)
  if (key === 'execute') handleExecute(row)
  if (key === 'rollback') handleRollback(row)
}

// ==================== 查看详情（Plan/Approval） ====================

const showViewModal = ref(false)
const viewData = ref<DeployTask | null>(null)
const viewLoading = ref(false)

const handleView = async (row: DeployTask) => {
  viewLoading.value = true
  showViewModal.value = true
  try {
    const res = await getDeployTask(row.id)
    viewData.value = res.data
  } catch {
    showViewModal.value = false
  } finally {
    viewLoading.value = false
  }
}

// ==================== 查看结果（Execution/Result） ====================

const showResultModal = ref(false)
const resultData = ref<DeployTask | null>(null)
const resultLoading = ref(false)

// 详情（单设备）弹窗
const showDeviceOutputModal = ref(false)
const currentDeviceResult = ref<DeviceDeployResult | null>(null)
const resultTab = ref<'raw' | 'parsed'>('raw')

const handleResult = async (row: DeployTask) => {
  resultLoading.value = true
  showResultModal.value = true
  try {
    const res = await getDeployTask(row.id)
    resultData.value = res.data
  } catch {
    showResultModal.value = false
  } finally {
    resultLoading.value = false
  }
}

const openDeviceOutput = (res: DeviceDeployResult) => {
  currentDeviceResult.value = res
  resultTab.value = 'raw'
  showDeviceOutputModal.value = true
}

// ==================== 创建下发任务 ====================

const showCreateModal = ref(false)
const createLoading = ref(false)
const createModel = ref({
  name: '',
  description: '',
  template_id: '',
  template_params: '{}',
  device_ids: [] as string[],
  change_description: '',
  impact_scope: '',
  rollback_plan: '',
  approver_ids: [] as string[],
})
const templateOptions = ref<{ label: string; value: string }[]>([])
const deviceOptions = ref<{ label: string; value: string }[]>([])
const userOptions = ref<{ label: string; value: string }[]>([])

const handleCreate = async () => {
  createLoading.value = true
  showCreateModal.value = true
  createModel.value = {
    name: '',
    description: '',
    template_id: '',
    template_params: '{}',
    device_ids: [],
    change_description: '',
    impact_scope: '',
    rollback_plan: '',
    approver_ids: [],
  }
  try {
    const [templatesRes, devicesRes, usersRes] = await Promise.all([
      getTemplates({ status: 'approved', page_size: 100 }),
      getDevices({ status: 'active', page_size: 100 }),
      getUsers({ page_size: 100 }),
    ])
    templateOptions.value = templatesRes.data.items.map((t: Template) => ({
      label: t.name,
      value: t.id,
    }))
    deviceOptions.value = devicesRes.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
    userOptions.value = usersRes.data.items.map((u: User) => ({
      label: formatUserDisplayName(u),
      value: u.id,
    }))
  } catch {
    showCreateModal.value = false
  } finally {
    createLoading.value = false
  }
}

const submitCreate = async () => {
  if (!createModel.value.name) {
    $alert.warning('请输入任务名称')
    return
  }
  if (!createModel.value.template_id) {
    $alert.warning('请选择模板')
    return
  }
  if (createModel.value.device_ids.length === 0) {
    $alert.warning('请选择设备')
    return
  }
  try {
    let templateParams = {}
    if (createModel.value.template_params) {
      try {
        templateParams = JSON.parse(createModel.value.template_params)
      } catch {
        $alert.warning('模板参数格式错误')
        return
      }
    }
    await createDeployTask({
      name: createModel.value.name,
      description: createModel.value.description || undefined,
      template_id: createModel.value.template_id,
      template_params: templateParams,
      device_ids: createModel.value.device_ids,
      change_description: createModel.value.change_description || undefined,
      impact_scope: createModel.value.impact_scope || undefined,
      rollback_plan: createModel.value.rollback_plan || undefined,
      approver_ids:
        createModel.value.approver_ids.length > 0 ? createModel.value.approver_ids : undefined,
    })
    $alert.success('下发任务创建成功')
    showCreateModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 审批 ====================

const showApproveModal = ref(false)
const approveModel = ref({
  task_id: '',
  task_name: '',
  level: 1,
  decision: 'approve' as 'approve' | 'reject',
  comment: '',
})

// ==================== OTP（手动输入） ====================

const showOtpModal = ref(false)
const otpLoading = ref(false)
const otpModel = ref({
  task_id: '',
  task_name: '',
  dept_id: '',
  device_group: '' as DeviceGroupType | '',
})

const otpAlertText = computed(() => {
  const name = otpModel.value.task_name || ''
  return `任务 "${name}" 需要 OTP 验证码才能继续执行。`
})

const otpInfoItems = computed(() => {
  return [
    { label: '部门ID', value: otpModel.value.dept_id },
    { label: '设备分组', value: String(otpModel.value.device_group || '-') },
  ]
})

const extractOtpRequiredGroups = (task: DeployTask): OtpRequiredGroup[] => {
  const taskResult = task.result as Record<string, unknown> | undefined
  if (!taskResult || typeof taskResult !== 'object') return []

  const groups = taskResult.otp_required_groups
  if (!Array.isArray(groups)) return []

  return groups
    .filter(
      (g): g is { dept_id: string; device_group: DeviceGroupType } =>
        g !== null &&
        typeof g === 'object' &&
        typeof (g as Record<string, unknown>).dept_id === 'string' &&
        typeof (g as Record<string, unknown>).device_group === 'string',
    )
    .map((g) => ({ dept_id: g.dept_id, device_group: g.device_group }))
}

const openOtpModal = (task: DeployTask) => {
  const groups = extractOtpRequiredGroups(task)
  if (!groups.length) {
    $alert.warning('任务需要 OTP，但未返回分组信息')
    return
  }
  const first = groups[0]!
  otpModel.value = {
    task_id: task.id,
    task_name: task.name,
    dept_id: first.dept_id,
    device_group: first.device_group,
  }
  showOtpModal.value = true
}

const submitOtpAndRetry = async (otpCode: string) => {
  if (!/^[0-9]{6,8}$/.test(otpCode)) {
    $alert.warning('请输入有效 OTP 验证码')
    return
  }

  otpLoading.value = true
  try {
    const cacheRes = await cacheOTP({
      dept_id: otpModel.value.dept_id,
      device_group: otpModel.value.device_group as DeviceGroupType,
      otp_code: otpCode,
    })

    if (!cacheRes.data?.success) {
      $alert.error(cacheRes.data?.message || 'OTP 缓存失败')
      return
    }

    const execRes = await executeDeployTask(otpModel.value.task_id)
    const updatedTask = execRes.data
    if (updatedTask.status === 'paused') {
      openOtpModal(updatedTask)
      return
    }

    showOtpModal.value = false
    $alert.success('OTP 已提交，下发任务已开始执行')
    tableRef.value?.reload()
  } catch {
    // Error handled
  } finally {
    otpLoading.value = false
  }
}

const handleApprove = (row: DeployTask) => {
  if (row.status !== 'pending' && row.status !== 'approving') {
    $alert.warning('该任务不在审批阶段')
    return
  }
  // 找到待审批的级别
  const pendingApproval = (row.approvals || []).find((a) => a.status === 'pending')
  approveModel.value = {
    task_id: row.id,
    task_name: row.name,
    level: pendingApproval?.level || 1,
    decision: 'approve',
    comment: '',
  }
  showApproveModal.value = true
}

const submitApprove = async () => {
  try {
    await approveDeployTask(approveModel.value.task_id, {
      level: approveModel.value.level,
      approve: approveModel.value.decision === 'approve',
      comment: approveModel.value.comment || undefined,
    })
    $alert.success(approveModel.value.decision === 'approve' ? '已批准' : '已拒绝')
    showApproveModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 执行 ====================

const handleExecute = (row: DeployTask) => {
  if (row.status !== 'approved') {
    $alert.warning('只能执行已批准的任务')
    return
  }
  const count = getTaskDeviceCount(row)
  dialog.warning({
    title: '执行下发',
    content: `确定要执行下发任务 "${row.name}" 吗？这将向 ${count} 台设备下发配置。`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await executeDeployTask(row.id)
        const task = res.data
        if (task.status === 'paused') {
          $alert.warning('需要输入 OTP 验证码')
          openOtpModal(task)
          return
        }
        $alert.success('下发任务已提交执行')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 回滚 ====================

const handleRollback = (row: DeployTask) => {
  if (row.status !== 'success' && row.status !== 'failed') {
    $alert.warning('只能回滚已完成或失败的任务')
    return
  }
  dialog.error({
    title: '回滚确认',
    content: `确定要回滚下发任务 "${row.name}" 吗？这将尝试撤销之前的配置变更。`,
    positiveText: '确认回滚',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await rollbackDeployTask(row.id)
        $alert.success('回滚任务已提交')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}
</script>

<template>
  <div class="deploy-management p-4">
    <ProTable
      ref="tableRef"
      title="配置下发任务"
      :columns="columns"
      :request="loadData"
      :row-key="(row: DeployTask) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索任务名称"
      :search-filters="searchFilters"
      @add="handleCreate"
      @context-menu-select="handleContextMenuSelect"
      show-add
      :scroll-x="1500"
    />

    <!-- 查看详情 Modal -->
    <n-modal
      v-model:show="showViewModal"
      preset="card"
      title="下发任务详情"
      style="width: 900px; max-height: 80vh; overflow: auto"
    >
      <div v-if="viewLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="viewData">
        <n-space vertical size="large">
          <n-descriptions :column="2" label-placement="left" bordered>
            <n-descriptions-item label="任务名称" :span="2">{{
              viewData.name
            }}</n-descriptions-item>
            <n-descriptions-item label="模板">{{
              viewData.template_name || '-'
            }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="statusColorMap[viewData.status]" size="small">
                {{ statusLabelMap[viewData.status] }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="Celery任务ID" :span="2">{{
              viewData.celery_task_id || '-'
            }}</n-descriptions-item>
            <n-descriptions-item label="设备数">{{
              getTaskDeviceCount(viewData)
            }}</n-descriptions-item>
            <n-descriptions-item label="创建人">{{
              viewData.created_by_name || '-'
            }}</n-descriptions-item>
            <n-descriptions-item label="变更说明" :span="2">
              <div style="white-space: pre-wrap; word-break: break-word">
                {{ viewData.change_description || '-' }}
              </div>
            </n-descriptions-item>
            <n-descriptions-item label="影响范围" :span="2">
              <div style="white-space: pre-wrap; word-break: break-word">
                {{ viewData.impact_scope || '-' }}
              </div>
            </n-descriptions-item>
            <n-descriptions-item label="回退方案" :span="2">
              <div style="white-space: pre-wrap; word-break: break-word">
                {{ viewData.rollback_plan || '-' }}
              </div>
            </n-descriptions-item>
            <n-descriptions-item label="错误信息" :span="2">
              <div style="white-space: pre-wrap; word-break: break-word">
                {{ viewData.error_message || '-' }}
              </div>
            </n-descriptions-item>
          </n-descriptions>

          <!-- 参数定义（模板参数 / 下发计划 / 目标设备） -->
          <div>
            <h4>参数定义</h4>
            <n-space vertical size="small">
              <div>
                <div style="font-weight: 600; margin-bottom: 6px">模板参数 (template_params)</div>
                <n-code
                  :code="viewData.template_params ? formatJson(viewData.template_params) : '{}'"
                  language="json"
                  style="max-height: 220px; overflow: auto"
                />
              </div>
              <div>
                <div style="font-weight: 600; margin-bottom: 6px">下发计划 (deploy_plan)</div>
                <n-code
                  :code="viewData.deploy_plan ? formatJson(viewData.deploy_plan) : '{}'"
                  language="json"
                  style="max-height: 220px; overflow: auto"
                />
              </div>
              <div>
                <div style="font-weight: 600; margin-bottom: 6px">目标设备 (target_devices)</div>
                <n-code
                  :code="viewData.target_devices ? formatJson(viewData.target_devices) : '{}'"
                  language="json"
                  style="max-height: 220px; overflow: auto"
                />
              </div>
            </n-space>
          </div>

          <!-- 审批流程 -->
          <div v-if="(viewData.approvals || []).length > 0">
            <h4>审批流程</h4>
            <n-timeline>
              <n-timeline-item
                v-for="approval in viewData.approvals || []"
                :key="approval.level"
                :type="
                  approval.status === 'approved'
                    ? 'success'
                    : approval.status === 'rejected'
                      ? 'error'
                      : 'default'
                "
                :title="`第 ${approval.level} 级审批`"
              >
                <p>审批人: {{ approval.approver_name || '待指定' }}</p>
                <p>
                  状态:
                  {{
                    approval.status === 'approved'
                      ? '已批准'
                      : approval.status === 'rejected'
                        ? '已拒绝'
                        : '待审批'
                  }}
                </p>
                <p v-if="approval.comment">备注: {{ approval.comment }}</p>
                <p v-if="approval.approved_at">时间: {{ formatDateTime(approval.approved_at) }}</p>
              </n-timeline-item>
            </n-timeline>
          </div>

          <!-- 渲染后的配置 -->
          <div v-if="viewData.rendered_content">
            <h4>渲染后配置</h4>
            <n-code
              :code="viewData.rendered_content"
              language="text"
              style="max-height: 300px; overflow: auto"
            />
          </div>
        </n-space>
      </template>
    </n-modal>

    <!-- 创建下发任务 Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" title="创建下发任务" style="width: 700px">
      <div v-if="createLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else>
        <n-space vertical style="width: 100%">
          <n-form-item label="任务名称">
            <n-input v-model:value="createModel.name" placeholder="请输入任务名称" />
          </n-form-item>
          <n-form-item label="选择模板">
            <n-select
              v-model:value="createModel.template_id"
              :options="templateOptions"
              placeholder="请选择配置模板"
              filterable
            />
          </n-form-item>
          <n-form-item label="模板参数 (JSON)">
            <n-input
              v-model:value="createModel.template_params"
              type="textarea"
              placeholder='{"key": "value"}'
              :rows="3"
              style="font-family: monospace"
            />
          </n-form-item>
          <n-form-item label="目标设备">
            <n-select
              v-model:value="createModel.device_ids"
              :options="deviceOptions"
              placeholder="请选择目标设备"
              filterable
              multiple
              max-tag-count="responsive"
            />
          </n-form-item>
          <n-form-item label="审批人 (三级)">
            <n-select
              v-model:value="createModel.approver_ids"
              :options="userOptions"
              placeholder="请选择审批人（按顺序）"
              filterable
              multiple
              :max-tag-count="3"
            />
          </n-form-item>
          <n-form-item label="变更说明">
            <n-input
              v-model:value="createModel.change_description"
              type="textarea"
              placeholder="描述本次变更的内容"
              :rows="2"
            />
          </n-form-item>
          <n-form-item label="影响范围">
            <n-input v-model:value="createModel.impact_scope" placeholder="描述影响范围" />
          </n-form-item>
          <n-form-item label="回退方案">
            <n-input
              v-model:value="createModel.rollback_plan"
              type="textarea"
              placeholder="描述回退方案"
              :rows="2"
            />
          </n-form-item>
        </n-space>
        <div style="margin-top: 20px; text-align: right">
          <n-space>
            <n-button @click="showCreateModal = false">取消</n-button>
            <n-button type="primary" @click="submitCreate">创建</n-button>
          </n-space>
        </div>
      </template>
    </n-modal>

    <!-- 审批 Modal -->
    <n-modal
      v-model:show="showApproveModal"
      preset="dialog"
      title="审批下发任务"
      style="width: 500px"
    >
      <div style="margin-bottom: 16px">
        <p>任务: {{ approveModel.task_name }}</p>
        <p>审批级别: 第 {{ approveModel.level }} 级</p>
      </div>
      <n-space vertical style="width: 100%">
        <n-form-item label="审批结果">
          <n-select
            v-model:value="approveModel.decision"
            :options="[
              { label: '批准', value: 'approve' },
              { label: '拒绝', value: 'reject' },
            ]"
          />
        </n-form-item>
        <n-form-item label="审批意见">
          <n-input
            v-model:value="approveModel.comment"
            type="textarea"
            placeholder="请输入审批意见（可选）"
            :rows="2"
          />
        </n-form-item>
      </n-space>
      <template #action>
        <n-button @click="showApproveModal = false">取消</n-button>
        <n-button
          :type="approveModel.decision === 'approve' ? 'success' : 'error'"
          @click="submitApprove"
        >
          {{ approveModel.decision === 'approve' ? '批准' : '拒绝' }}
        </n-button>
      </template>
    </n-modal>

    <!-- OTP 输入 Modal（通用组件） -->
    <OtpModal
      v-model:show="showOtpModal"
      :loading="otpLoading"
      :title="'需要 OTP 验证码'"
      :alert-title="'需要 OTP'"
      :alert-text="otpAlertText"
      :info-items="otpInfoItems"
      confirm-text="提交并继续"
      @confirm="submitOtpAndRetry"
    />

    <!-- 查看结果 Modal -->
    <n-modal
      v-model:show="showResultModal"
      preset="card"
      title="下发执行结果"
      style="width: 900px; max-height: 80vh"
    >
      <div v-if="resultLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="resultData">
        <n-space vertical>
          <!-- 汇总信息 -->
          <n-space>
            <n-tag :type="statusColorMap[resultData.status]">
              状态: {{ statusLabelMap[resultData.status] }}
            </n-tag>
            <n-tag type="success">成功: {{ resultData.success_count || 0 }}</n-tag>
            <n-tag type="error">失败: {{ resultData.failed_count || 0 }}</n-tag>
          </n-space>

          <n-table :bordered="false" :single-line="false">
            <thead>
              <tr>
                <th>设备</th>
                <th>状态</th>
                <th>执行时间</th>
                <th>简略信息</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="result in resultData.device_results || []" :key="result.device_id">
                <td>{{ result.device_name || result.device_id }}</td>
                <td>
                  <n-tag
                    :type="
                      result.status === 'success'
                        ? 'success'
                        : result.status === 'failed'
                          ? 'error'
                          : 'default'
                    "
                    size="small"
                  >
                    {{
                      result.status === 'success'
                        ? '成功'
                        : result.status === 'failed'
                          ? '失败'
                          : '待执行'
                    }}
                  </n-tag>
                </td>
                <td>{{ formatDateTime(result.executed_at) }}</td>
                <td
                  style="
                    max-width: 300px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                  "
                >
                  {{ result.error || (result.output ? '有输出内容' : '-') }}
                </td>
                <td>
                  <n-button size="tiny" secondary @click="openDeviceOutput(result)">
                    查看输出
                  </n-button>
                </td>
              </tr>
            </tbody>
          </n-table>
        </n-space>
      </template>
    </n-modal>

    <!-- 设备详细输出 Modal -->
    <n-modal
      v-model:show="showDeviceOutputModal"
      preset="card"
      :title="`设备输出: ${currentDeviceResult?.device_name || currentDeviceResult?.device_id}`"
      style="width: 800px; max-height: 80vh"
    >
      <template v-if="currentDeviceResult">
        <n-tabs v-model:value="resultTab" type="line">
          <n-tab-pane name="raw" tab="原始输出">
            <div class="code-scroll">
              <n-code
                :code="currentDeviceResult.output || currentDeviceResult.error || '(无输出)'"
                language="text"
              />
            </div>
          </n-tab-pane>
          <n-tab-pane name="parsed" tab="结构化数据">
            <n-result
              status="info"
              title="暂无结构化数据"
              description="配置下发任务暂不支持 TextFSM 解析，请查看原始输出。"
            />
          </n-tab-pane>
        </n-tabs>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.deploy-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}

.code-scroll {
  max-height: 55vh;
  overflow: auto;
  max-width: 100%;
}
</style>
