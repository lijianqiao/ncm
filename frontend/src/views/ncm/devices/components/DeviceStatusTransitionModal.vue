<!--
@Author: li
@Email: lijianqiao2906@live.com
@FileName: DeviceStatusTransitionModal.vue
@DateTime: 2026-01-12
@Docs: 设备状态流转弹窗组件
-->

<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NForm, NFormItem, NSelect, NInput, NButton } from 'naive-ui'
import { DeviceStatusOptions, DeviceStatusLabels } from '@/types/enum-labels'
import type { DeviceStatus } from '@/types/enums'

interface Props {
  /** 弹窗显示状态 */
  show: boolean
  /** 设备 ID */
  deviceId?: string
  /** 设备名称 */
  deviceName?: string
  /** 当前状态 */
  currentStatus?: DeviceStatus
  /** 是否批量模式 */
  batch?: boolean
  /** 批量选中的设备数量 */
  selectedCount?: number
}

const props = withDefaults(defineProps<Props>(), {
  show: false,
  deviceId: '',
  deviceName: '',
  currentStatus: undefined,
  batch: false,
  selectedCount: 0,
})

const emit = defineEmits<{
  'update:show': [value: boolean]
  'submit': [toStatus: DeviceStatus, reason: string]
}>()

// 内部状态
const toStatus = ref<DeviceStatus | null>(null)
const reason = ref('')
const statusOptions = DeviceStatusOptions
const statusLabelMap = DeviceStatusLabels

// 监听弹窗打开重置状态
watch(
  () => props.show,
  (val) => {
    if (val) {
      toStatus.value = props.currentStatus || null
      reason.value = ''
    }
  },
)

const handleClose = () => {
  emit('update:show', false)
}

const handleSubmit = () => {
  if (!toStatus.value) return
  emit('submit', toStatus.value, reason.value)
}
</script>

<template>
  <n-modal
    :show="show"
    preset="dialog"
    :title="batch ? '批量状态流转' : '设备状态流转'"
    @update:show="emit('update:show', $event)"
  >
    <div class="transition-info">
      <template v-if="batch">
        <span>已选择 {{ selectedCount }} 个设备</span>
      </template>
      <template v-else>
        <span>设备: {{ deviceName }}</span>
        <br />
        <span>当前状态: {{ currentStatus ? statusLabelMap[currentStatus] : '-' }}</span>
      </template>
    </div>
    <n-form label-placement="left" label-width="80">
      <n-form-item label="目标状态">
        <n-select v-model:value="toStatus" :options="statusOptions" />
      </n-form-item>
      <n-form-item label="变更原因">
        <n-input
          v-model:value="reason"
          type="textarea"
          placeholder="请输入变更原因（可选）"
          :rows="2"
        />
      </n-form-item>
    </n-form>
    <template #action>
      <n-button @click="handleClose">取消</n-button>
      <n-button type="primary" @click="handleSubmit">确认</n-button>
    </template>
  </n-modal>
</template>

<style scoped>
.transition-info {
  margin-bottom: 16px;
}
</style>
