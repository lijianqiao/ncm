<script setup lang="ts">
import { ref, h, onUnmounted } from 'vue'
import {
  NButton,
  NModal,
  useDialog,
  type DataTableColumns,
  NTag,
  NSelect,
  NSpace,
  NCode,
  NProgress,
  NAlert,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getBackups,
  getBackupContent,
  deleteBackup,
  backupDevice,
  batchBackup,
  getBackupTaskStatus,
  type Backup,
  type BackupSearchParams,
  type BackupType,
  type BackupTaskStatus,
} from '@/api/backups'
import { getDevices, type Device } from '@/api/devices'
import { getDeviceLatestDiff, type DiffResponse } from '@/api/diff'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'BackupManagement',
})

const dialog = useDialog()
const tableRef = ref()

// ==================== 常量定义 ====================

const backupTypeOptions = [
  { label: 'Running', value: 'running' },
  { label: 'Startup', value: 'startup' },
  { label: 'Full', value: 'full' },
]

const backupTypeLabelMap: Record<BackupType, string> = {
  running: 'Running',
  startup: 'Startup',
  full: 'Full',
}

const backupTypeColorMap: Record<BackupType, 'info' | 'success' | 'warning'> = {
  running: 'info',
  startup: 'success',
  full: 'warning',
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
    key: 'device_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.device_name || '-',
  },
  {
    title: '备份类型',
    key: 'backup_type',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: backupTypeColorMap[row.backup_type], bordered: false, size: 'small' },
        { default: () => backupTypeLabelMap[row.backup_type] },
      )
    },
  },
  {
    title: '配置 Hash',
    key: 'config_hash',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.config_hash.substring(0, 12) + '...',
  },
  {
    title: '文件大小',
    key: 'file_size',
    width: 100,
    render: (row) => formatFileSize(row.file_size),
  },
  {
    title: '备份时间',
    key: 'created_at',
    width: 180,
    render: (row) => formatDateTime(row.created_at),
  },
]

// ==================== 搜索筛选 ====================

const searchFilters: FilterConfig[] = [
  { key: 'backup_type', placeholder: '备份类型', options: backupTypeOptions, width: 120 },
]

// ==================== 数据加载 ====================

const loadData = async (params: BackupSearchParams) => {
  const res = await getBackups(params)
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

const handleContextMenuSelect = (key: string | number, row: Backup) => {
  if (key === 'view') handleViewContent(row)
  if (key === 'diff') handleViewDiff(row)
  if (key === 'delete') handleDelete(row)
}

// ==================== 查看配置内容 ====================

const showContentModal = ref(false)
const contentData = ref({
  device_name: '',
  backup_type: 'running' as BackupType,
  content: '',
  config_hash: '',
  created_at: '',
})
const contentLoading = ref(false)

const handleViewContent = async (row: Backup) => {
  contentLoading.value = true
  showContentModal.value = true
  try {
    const res = await getBackupContent(row.id)
    contentData.value = res.data
  } catch {
    showContentModal.value = false
  } finally {
    contentLoading.value = false
  }
}

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
    content: `确定要删除该备份吗？（设备: ${row.device_name}）`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteBackup(row.id)
        $alert.success('备份已删除')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 手动备份 ====================

const showBackupModal = ref(false)
const backupModel = ref({
  device_id: '',
})
const deviceOptions = ref<{ label: string; value: string }[]>([])
const deviceLoading = ref(false)

const handleManualBackup = async () => {
  deviceLoading.value = true
  showBackupModal.value = true
  try {
    const res = await getDevices({ page_size: 500, status: 'running' })
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
  try {
    await backupDevice(backupModel.value.device_id)
    $alert.success('备份任务已提交')
    showBackupModal.value = false
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

// ==================== 批量备份 ====================

const showBatchBackupModal = ref(false)
const batchBackupModel = ref({
  device_ids: [] as string[],
  backup_type: 'running' as BackupType,
})
const batchTaskStatus = ref<BackupTaskStatus | null>(null)
const batchTaskPolling = ref<ReturnType<typeof setInterval> | null>(null)

const handleBatchBackup = async () => {
  deviceLoading.value = true
  showBatchBackupModal.value = true
  batchTaskStatus.value = null
  try {
    const res = await getDevices({ page_size: 500, status: 'running' })
    deviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
  } catch {
    showBatchBackupModal.value = false
  } finally {
    deviceLoading.value = false
  }
}

const submitBatchBackup = async () => {
  if (batchBackupModel.value.device_ids.length === 0) {
    $alert.warning('请选择设备')
    return
  }
  try {
    const res = await batchBackup({
      device_ids: batchBackupModel.value.device_ids,
      backup_type: batchBackupModel.value.backup_type,
    })
    $alert.success('批量备份任务已提交')
    // 开始轮询任务状态
    startPollingTaskStatus(res.data.task_id)
  } catch {
    // Error handled
  }
}

const startPollingTaskStatus = (taskId: string) => {
  batchTaskStatus.value = {
    task_id: taskId,
    status: 'pending',
    progress: 0,
    result: null,
    error: null,
  }

  batchTaskPolling.value = setInterval(async () => {
    try {
      const res = await getBackupTaskStatus(taskId)
      batchTaskStatus.value = res.data

      if (res.data.status === 'success' || res.data.status === 'failed') {
        stopPollingTaskStatus()
        tableRef.value?.reload()
      }
    } catch {
      stopPollingTaskStatus()
    }
  }, 2000)
}

const stopPollingTaskStatus = () => {
  if (batchTaskPolling.value) {
    clearInterval(batchTaskPolling.value)
    batchTaskPolling.value = null
  }
}

onUnmounted(() => {
  stopPollingTaskStatus()
})

const closeBatchBackupModal = () => {
  stopPollingTaskStatus()
  showBatchBackupModal.value = false
  batchBackupModel.value = { device_ids: [], backup_type: 'running' }
  batchTaskStatus.value = null
}
</script>

<template>
  <div class="backup-management p-4">
    <ProTable
      ref="tableRef"
      title="配置备份列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Backup) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索设备名称"
      :search-filters="searchFilters"
      @context-menu-select="handleContextMenuSelect"
      :scroll-x="1000"
    >
      <template #toolbar-left>
        <n-space>
          <n-button type="primary" @click="handleManualBackup">手动备份</n-button>
          <n-button type="info" @click="handleBatchBackup">批量备份</n-button>
        </n-space>
      </template>
    </ProTable>

    <!-- 查看配置内容 Modal -->
    <n-modal
      v-model:show="showContentModal"
      preset="card"
      title="配置内容"
      style="width: 900px; max-height: 80vh"
    >
      <div v-if="contentLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else>
        <div style="margin-bottom: 16px">
          <n-space>
            <span>设备: {{ contentData.device_name }}</span>
            <n-tag :type="backupTypeColorMap[contentData.backup_type]" size="small">
              {{ backupTypeLabelMap[contentData.backup_type] }}
            </n-tag>
            <span>Hash: {{ contentData.config_hash }}</span>
            <span>时间: {{ formatDateTime(contentData.created_at) }}</span>
          </n-space>
        </div>
        <n-code
          :code="contentData.content"
          language="text"
          style="max-height: 500px; overflow: auto"
        />
      </template>
    </n-modal>

    <!-- 配置差异 Modal -->
    <n-modal
      v-model:show="showDiffModal"
      preset="card"
      title="配置差异对比"
      style="width: 900px; max-height: 80vh"
    >
      <div v-if="diffLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else-if="diffData">
        <div style="margin-bottom: 16px">
          <n-space>
            <span>设备: {{ diffData.device_name }}</span>
            <n-tag v-if="diffData.has_changes" type="warning" size="small">有变更</n-tag>
            <n-tag v-else type="success" size="small">无变更</n-tag>
          </n-space>
        </div>
        <div v-if="diffData.has_changes && diffData.diff_content">
          <n-code
            :code="diffData.diff_content"
            language="diff"
            style="max-height: 500px; overflow: auto"
          />
        </div>
        <n-alert v-else type="success" title="配置无变化">
          最新两次备份的配置内容完全一致
        </n-alert>
      </template>
    </n-modal>

    <!-- 手动备份 Modal -->
    <n-modal v-model:show="showBackupModal" preset="dialog" title="手动备份" style="width: 500px">
      <div v-if="deviceLoading" style="text-align: center; padding: 20px">加载设备列表...</div>
      <template v-else>
        <n-select
          v-model:value="backupModel.device_id"
          :options="deviceOptions"
          placeholder="请选择要备份的设备"
          filterable
        />
      </template>
      <template #action>
        <n-button @click="showBackupModal = false">取消</n-button>
        <n-button type="primary" @click="submitManualBackup">开始备份</n-button>
      </template>
    </n-modal>

    <!-- 批量备份 Modal -->
    <n-modal
      v-model:show="showBatchBackupModal"
      preset="card"
      title="批量备份"
      style="width: 600px"
      :closable="!batchTaskPolling"
      :mask-closable="!batchTaskPolling"
      @close="closeBatchBackupModal"
    >
      <div v-if="deviceLoading" style="text-align: center; padding: 20px">加载设备列表...</div>
      <template v-else-if="!batchTaskStatus">
        <n-space vertical style="width: 100%">
          <div>
            <label style="display: block; margin-bottom: 8px">选择设备:</label>
            <n-select
              v-model:value="batchBackupModel.device_ids"
              :options="deviceOptions"
              placeholder="请选择要备份的设备"
              filterable
              multiple
              max-tag-count="responsive"
            />
          </div>
          <div>
            <label style="display: block; margin-bottom: 8px">备份类型:</label>
            <n-select
              v-model:value="batchBackupModel.backup_type"
              :options="backupTypeOptions"
            />
          </div>
        </n-space>
        <div style="margin-top: 20px; text-align: right">
          <n-space>
            <n-button @click="closeBatchBackupModal">取消</n-button>
            <n-button type="primary" @click="submitBatchBackup">开始批量备份</n-button>
          </n-space>
        </div>
      </template>
      <template v-else>
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ batchTaskStatus.task_id }}</p>
            <p>
              状态:
              <n-tag
                :type="
                  batchTaskStatus.status === 'success'
                    ? 'success'
                    : batchTaskStatus.status === 'failed'
                      ? 'error'
                      : 'info'
                "
              >
                {{ batchTaskStatus.status }}
              </n-tag>
            </p>
          </div>
          <n-progress
            type="line"
            :percentage="batchTaskStatus.progress"
            :status="
              batchTaskStatus.status === 'success'
                ? 'success'
                : batchTaskStatus.status === 'failed'
                  ? 'error'
                  : 'default'
            "
          />
          <template v-if="batchTaskStatus.result">
            <div>
              <p>总数: {{ batchTaskStatus.result.total }}</p>
              <p>成功: {{ batchTaskStatus.result.success_count }}</p>
              <p>失败: {{ batchTaskStatus.result.failed_count }}</p>
            </div>
            <div v-if="batchTaskStatus.result.failed_devices.length > 0">
              <p>失败详情:</p>
              <ul>
                <li v-for="item in batchTaskStatus.result.failed_devices" :key="item.device_id">
                  设备 {{ item.device_id }}: {{ item.error }}
                </li>
              </ul>
            </div>
          </template>
          <n-alert v-if="batchTaskStatus.error" type="error" :title="batchTaskStatus.error" />
        </n-space>
        <div
          v-if="batchTaskStatus.status === 'success' || batchTaskStatus.status === 'failed'"
          style="margin-top: 20px; text-align: right"
        >
          <n-button @click="closeBatchBackupModal">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.backup-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
