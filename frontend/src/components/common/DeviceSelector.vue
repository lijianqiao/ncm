<script setup lang="ts">
import { watch, onMounted } from 'vue'
import { NSelect, NSpace, NButton } from 'naive-ui'
import { useDeviceOptions } from '@/composables/useDeviceOptions'
import type { Device, DeviceStatus } from '@/api/devices'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    status?: DeviceStatus
    label?: string
    placeholder?: string
    disabled?: boolean
    pageSize?: number
  }>(),
  {
    status: 'active',
    label: '选择设备',
    placeholder: '请选择设备',
    disabled: false,
    pageSize: 500,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
  (e: 'update:devices', value: Device[]): void
}>()

const {
  deviceOptions,
  devicesById,
  loading,
  load: loadDevices,
} = useDeviceOptions({
  status: props.status,
  pageSize: props.pageSize,
  immediate: false, // 手动触发加载，避免不必要的请求
})

// 监听选中值变化，抛出完整的 Device 对象
watch(
  () => props.modelValue,
  (newVal) => {
    const selectedDevices = newVal
      .map((id) => devicesById.value[id])
      .filter((d): d is Device => !!d)
    emit('update:devices', selectedDevices)
  },
  { deep: true },
)

const handleSelectAll = () => {
  const allIds = deviceOptions.value.map((opt) => opt.value)
  emit('update:modelValue', allIds)
}

const handleClear = () => {
  emit('update:modelValue', [])
}

// 暴露 load 方法给父组件（如果需要手动刷新）
defineExpose({
  load: loadDevices,
})

// 组件挂载时自动加载
onMounted(() => {
  loadDevices()
})
</script>

<template>
  <div class="device-selector">
    <div class="ds-header">
      <label v-if="label" class="ds-label">{{ label }}</label>
      <n-space size="small">
        <n-button size="tiny" type="primary" secondary @click="handleSelectAll" :disabled="disabled || loading">
          全选
        </n-button>
        <n-button size="tiny" secondary @click="handleClear" :disabled="disabled || loading">
          清空
        </n-button>
        <n-button size="tiny" secondary @click="() => loadDevices(true)" :loading="loading" :disabled="disabled">
          刷新
        </n-button>
      </n-space>
    </div>
    <n-select :value="modelValue" @update:value="(val) => emit('update:modelValue', val)" multiple filterable
      :options="deviceOptions" :loading="loading" :placeholder="placeholder" :disabled="disabled"
      max-tag-count="responsive" virtual-scroll />
  </div>
</template>

<style scoped>
.device-selector {
  width: 100%;
}

.ds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ds-label {
  font-weight: 500;
}
</style>
