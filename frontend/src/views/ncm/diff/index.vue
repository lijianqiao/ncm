<script setup lang="ts">
import { ref } from 'vue'
import {
  NButton,
  NSpace,
  NCard,
  NSelect,
  NAlert,
  NTag,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import { getDeviceLatestDiff, type DiffResponse } from '@/api/diff'
import { getDevices, type Device } from '@/api/devices'
import { formatDateTime } from '@/utils/date'
import UnifiedDiffViewer from '@/components/common/UnifiedDiffViewer.vue'

defineOptions({
  name: 'DiffManagement',
})

// ==================== 设备选项 ====================

const deviceOptions = ref<{ label: string; value: string }[]>([])
const deviceLoading = ref(false)
const selectedDeviceId = ref('')

const fetchDevices = async () => {
  deviceLoading.value = true
  try {
    const res = await getDevices({ status: 'active', page_size: 100 })
    deviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
  } catch {
    // Error handled
  } finally {
    deviceLoading.value = false
  }
}

// 初始加载
fetchDevices()

// ==================== 差异查询 ====================

const diffData = ref<DiffResponse | null>(null)
const diffLoading = ref(false)

const handleFetchDiff = async () => {
  if (!selectedDeviceId.value) {
    $alert.warning('请选择设备')
    return
  }
  diffLoading.value = true
  diffData.value = null
  try {
    const res = await getDeviceLatestDiff(selectedDeviceId.value)
    diffData.value = res.data
  } catch {
    // Error handled
  } finally {
    diffLoading.value = false
  }
}
</script>

<template>
  <div class="diff-management p-4">
    <n-card title="配置差异对比" :bordered="false">
      <n-space vertical size="large" style="width: 100%">
        <!-- 设备选择 -->
        <n-space>
          <n-select
            v-model:value="selectedDeviceId"
            :options="deviceOptions"
            :loading="deviceLoading"
            placeholder="请选择设备"
            filterable
            style="width: 400px"
          />
          <n-button type="primary" :loading="diffLoading" @click="handleFetchDiff">
            获取最新配置差异
          </n-button>
        </n-space>

        <!-- 差异结果 -->
        <template v-if="diffData">
          <n-card size="small" :bordered="true">
            <n-space justify="space-between" align="center">
              <n-space>
                <span><strong>设备:</strong> {{ diffData.device_name }}</span>
                <n-tag v-if="diffData.has_changes" type="warning" size="small">有变更</n-tag>
                <n-tag v-else type="success" size="small">无变更</n-tag>
              </n-space>
              <n-space v-if="diffData.created_at">
                <span>对比时间: {{ formatDateTime(diffData.created_at) }}</span>
              </n-space>
            </n-space>
          </n-card>

          <template v-if="diffData.has_changes && diffData.diff_content">
            <n-card size="small" title="差异详情" :bordered="true">
              <template #header-extra>
                <n-space>
                  <span v-if="diffData.old_hash">旧版本: {{ diffData.old_hash?.substring(0, 8) }}...</span>
                  <span v-if="diffData.new_hash">新版本: {{ diffData.new_hash?.substring(0, 8) }}...</span>
                </n-space>
              </template>
              <UnifiedDiffViewer :diff="diffData.diff_content" :max-height="600" />
            </n-card>
          </template>

          <n-alert v-else-if="!diffData.has_changes" type="success" title="配置无变化">
            该设备最新两次备份的配置内容完全一致，没有检测到任何变更。
          </n-alert>

          <n-alert v-else-if="!diffData.old_backup_id || !diffData.new_backup_id" type="info" title="备份不足">
            该设备备份记录不足两次，无法进行差异对比。请先确保设备至少有两次成功的配置备份。
          </n-alert>
        </template>

        <!-- 空状态 -->
        <template v-else-if="!diffLoading">
          <n-alert type="info" title="使用说明">
            选择设备后点击"获取最新配置差异"按钮，系统将自动对比该设备最新两次备份配置的差异。
            <br />
            <br />
            差异内容以 Unified Diff 格式展示：
            <ul style="margin: 8px 0 0 20px">
              <li><code style="color: #d03050">- 红色行</code> 表示被删除的内容</li>
              <li><code style="color: #18a058">+ 绿色行</code> 表示新增的内容</li>
            </ul>
          </n-alert>
        </template>
      </n-space>
    </n-card>
  </div>
</template>

<style scoped>
.diff-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
