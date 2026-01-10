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
} from '@/api/deploy'
import { getTemplates, type Template } from '@/api/templates'
import { getDevices, type Device } from '@/api/devices'
import { getUsers, type User } from '@/api/users'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

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
  { label: '执行中', value: 'executing' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '已回滚', value: 'rollback' },
]

const statusLabelMap: Record<DeployTaskStatus, string> = {
  pending: '待审批',
  approving: '审批中',
  approved: '已批准',
  rejected: '已拒绝',
  executing: '执行中',
  success: '成功',
  failed: '失败',
  rollback: '已回滚',
}

const statusColorMap: Record<DeployTaskStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'default',
  approving: 'info',
  approved: 'info',
  rejected: 'error',
  executing: 'warning',
  success: 'success',
  failed: 'error',
  rollback: 'warning',
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
    render: (row) => row.device_ids.length,
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
    title: '创建时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
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
  { label: '审批', key: 'approve' },
  { label: '执行', key: 'execute' },
  { label: '回滚', key: 'rollback' },
]

const handleContextMenuSelect = (key: string | number, row: DeployTask) => {
  if (key === 'view') handleView(row)
  if (key === 'approve') handleApprove(row)
  if (key === 'execute') handleExecute(row)
  if (key === 'rollback') handleRollback(row)
}

// ==================== 查看详情 ====================

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
      getDevices({ status: 'running', page_size: 500 }),
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
      label: u.nickname || u.username,
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
      approver_ids: createModel.value.approver_ids.length > 0 ? createModel.value.approver_ids : undefined,
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
  approve: true,
  comment: '',
})

const handleApprove = (row: DeployTask) => {
  if (row.status !== 'pending' && row.status !== 'approving') {
    $alert.warning('该任务不在审批阶段')
    return
  }
  // 找到待审批的级别
  const pendingApproval = row.approvals.find((a) => a.status === 'pending')
  approveModel.value = {
    task_id: row.id,
    task_name: row.name,
    level: pendingApproval?.level || 1,
    approve: true,
    comment: '',
  }
  showApproveModal.value = true
}

const submitApprove = async () => {
  try {
    await approveDeployTask(approveModel.value.task_id, {
      level: approveModel.value.level,
      approve: approveModel.value.approve,
      comment: approveModel.value.comment || undefined,
    })
    $alert.success(approveModel.value.approve ? '已批准' : '已拒绝')
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
  dialog.warning({
    title: '执行下发',
    content: `确定要执行下发任务 "${row.name}" 吗？这将向 ${row.device_ids.length} 台设备下发配置。`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await executeDeployTask(row.id)
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
      :scroll-x="1000"
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
            <n-descriptions-item label="任务名称" :span="2">{{ viewData.name }}</n-descriptions-item>
            <n-descriptions-item label="模板">{{ viewData.template_name || '-' }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="statusColorMap[viewData.status]" size="small">
                {{ statusLabelMap[viewData.status] }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="设备数">{{ viewData.device_ids.length }}</n-descriptions-item>
            <n-descriptions-item label="创建人">{{ viewData.created_by_name || '-' }}</n-descriptions-item>
            <n-descriptions-item label="变更说明" :span="2">{{ viewData.change_description || '-' }}</n-descriptions-item>
            <n-descriptions-item label="影响范围" :span="2">{{ viewData.impact_scope || '-' }}</n-descriptions-item>
            <n-descriptions-item label="回退方案" :span="2">{{ viewData.rollback_plan || '-' }}</n-descriptions-item>
          </n-descriptions>

          <!-- 审批流程 -->
          <div v-if="viewData.approvals.length > 0">
            <h4>审批流程</h4>
            <n-timeline>
              <n-timeline-item
                v-for="approval in viewData.approvals"
                :key="approval.level"
                :type="approval.status === 'approved' ? 'success' : approval.status === 'rejected' ? 'error' : 'default'"
                :title="`第 ${approval.level} 级审批`"
              >
                <p>审批人: {{ approval.approver_name || '待指定' }}</p>
                <p>状态: {{ approval.status === 'approved' ? '已批准' : approval.status === 'rejected' ? '已拒绝' : '待审批' }}</p>
                <p v-if="approval.comment">备注: {{ approval.comment }}</p>
                <p v-if="approval.approved_at">时间: {{ formatDateTime(approval.approved_at) }}</p>
              </n-timeline-item>
            </n-timeline>
          </div>

          <!-- 渲染后的配置 -->
          <div v-if="viewData.rendered_content">
            <h4>渲染后配置</h4>
            <n-code :code="viewData.rendered_content" language="text" style="max-height: 300px; overflow: auto" />
          </div>

          <!-- 设备执行结果 -->
          <div v-if="viewData.device_results.length > 0">
            <h4>设备执行结果</h4>
            <n-table :bordered="false" :single-line="false">
              <thead>
                <tr>
                  <th>设备</th>
                  <th>状态</th>
                  <th>执行时间</th>
                  <th>输出/错误</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="result in viewData.device_results" :key="result.device_id">
                  <td>{{ result.device_name || result.device_id }}</td>
                  <td>
                    <n-tag
                      :type="result.status === 'success' ? 'success' : result.status === 'failed' ? 'error' : 'default'"
                      size="small"
                    >
                      {{ result.status === 'success' ? '成功' : result.status === 'failed' ? '失败' : '待执行' }}
                    </n-tag>
                  </td>
                  <td>{{ formatDateTime(result.executed_at) }}</td>
                  <td>{{ result.error || result.output || '-' }}</td>
                </tr>
              </tbody>
            </n-table>
          </div>
        </n-space>
      </template>
    </n-modal>

    <!-- 创建下发任务 Modal -->
    <n-modal
      v-model:show="showCreateModal"
      preset="card"
      title="创建下发任务"
      style="width: 700px"
    >
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
            <n-input
              v-model:value="createModel.impact_scope"
              placeholder="描述影响范围"
            />
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
    <n-modal v-model:show="showApproveModal" preset="dialog" title="审批下发任务" style="width: 500px">
      <div style="margin-bottom: 16px">
        <p>任务: {{ approveModel.task_name }}</p>
        <p>审批级别: 第 {{ approveModel.level }} 级</p>
      </div>
      <n-space vertical style="width: 100%">
        <n-form-item label="审批结果">
          <n-select
            v-model:value="approveModel.approve"
            :options="[
              { label: '批准', value: true },
              { label: '拒绝', value: false },
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
          :type="approveModel.approve ? 'success' : 'error'"
          @click="submitApprove"
        >
          {{ approveModel.approve ? '批准' : '拒绝' }}
        </n-button>
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
</style>
