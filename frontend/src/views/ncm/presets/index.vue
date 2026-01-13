<script setup lang="ts">
/**
 * 快捷操作页面 - 使用预设模板执行设备命令
 */
import { ref, computed, onMounted } from 'vue'
import {
  NCard,
  NGrid,
  NGridItem,
  NModal,
  NForm,
  NFormItem,
  NSelect,
  NInput,
  NInputNumber,
  NButton,
  NSpace,
  NSpin,
  NTabs,
  NTabPane,
  NCode,
  NResult,
  NTag,
  NPopover,
} from 'naive-ui'
import {
  getPresets,
  getPreset,
  executePreset,
  type PresetInfo,
  type PresetDetail,
  type PresetExecuteResult,
} from '@/api/presets'
import { getDeviceOptions, type Device } from '@/api/devices'
import { $alert } from '@/utils/alert'

defineOptions({
  name: 'PresetOperations',
})

// 预设列表
const presets = ref<PresetInfo[]>([])
const loading = ref(false)

// 当前选择的预设
const currentPreset = ref<PresetDetail | null>(null)
const showExecuteModal = ref(false)

// 执行表单
const deviceOptions = ref<{ label: string; value: string; vendor: string }[]>([])
const deviceLoading = ref(false)
const selectedDeviceId = ref<string | null>(null)
const formParams = ref<Record<string, unknown>>({})
const executing = ref(false)

// 执行结果
const showResultModal = ref(false)
const executeResult = ref<PresetExecuteResult | null>(null)
const resultTab = ref<'raw' | 'parsed'>('raw')

// 获取预设列表
const loadPresets = async () => {
  loading.value = true
  try {
    const res = await getPresets()
    presets.value = res.data
  } catch {
    // Error handled
  } finally {
    loading.value = false
  }
}

// 按分类分组
const showPresets = computed(() => presets.value.filter((p) => p.category === 'show'))
const configPresets = computed(() => presets.value.filter((p) => p.category === 'config'))

// 获取设备列表
const loadDevices = async () => {
  if (deviceOptions.value.length > 0) return
  deviceLoading.value = true
  try {
    const res = await getDeviceOptions({ status: 'active' })
    deviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address}) - ${d.vendor || 'Unknown'}`,
      value: d.id,
      vendor: d.vendor || '',
    }))
  } catch {
    // Error handled
  } finally {
    deviceLoading.value = false
  }
}

// 打开执行弹窗
const openExecuteModal = async (preset: PresetInfo) => {
  try {
    const res = await getPreset(preset.id)
    currentPreset.value = res.data
    formParams.value = {}
    selectedDeviceId.value = null
    showExecuteModal.value = true
    await loadDevices()
  } catch {
    // Error handled
  }
}

// 获取过滤后的设备选项（根据预设支持的厂商）
const filteredDeviceOptions = computed(() => {
  if (!currentPreset.value) return deviceOptions.value
  const supportedVendors = currentPreset.value.supported_vendors
  return deviceOptions.value.filter((d) => supportedVendors.includes(d.vendor))
})

// 根据 JSON Schema 生成表单字段
const schemaProperties = computed(() => {
  if (!currentPreset.value?.parameters_schema) return []
  const schema = currentPreset.value.parameters_schema as {
    properties?: Record<
      string,
      {
        type?: string
        title?: string
        description?: string
        minimum?: number
        maximum?: number
        maxLength?: number
      }
    >
    required?: string[]
  }
  const props = schema.properties || {}
  const required = schema.required || []
  return Object.entries(props).map(([key, value]) => ({
    key,
    title: value.title || key,
    type: value.type || 'string',
    description: value.description,
    required: required.includes(key),
    minimum: value.minimum,
    maximum: value.maximum,
    maxLength: value.maxLength,
  }))
})

// 执行预设
const handleExecute = async () => {
  if (!currentPreset.value || !selectedDeviceId.value) {
    $alert.warning('请选择目标设备')
    return
  }

  // 校验必填参数
  for (const prop of schemaProperties.value) {
    if (prop.required && !formParams.value[prop.key]) {
      $alert.warning(`请填写 ${prop.title}`)
      return
    }
  }

  executing.value = true
  try {
    const res = await executePreset(currentPreset.value.id, {
      device_id: selectedDeviceId.value,
      params: formParams.value,
    })
    executeResult.value = res.data
    showExecuteModal.value = false
    showResultModal.value = true
    resultTab.value = 'raw'
  } catch {
    // Error handled
  } finally {
    executing.value = false
  }
}

// 格式化解析结果
const formattedParsedOutput = computed(() => {
  if (!executeResult.value?.parsed_output) return ''
  try {
    return JSON.stringify(executeResult.value.parsed_output, null, 2)
  } catch {
    return String(executeResult.value.parsed_output)
  }
})

onMounted(() => {
  loadPresets()
})
</script>

<template>
  <div class="preset-operations">
    <n-spin :show="loading">
      <!-- 查看类操作 -->
      <n-card title="查看类操作" size="small" style="margin-bottom: 16px">
        <n-grid :cols="4" :x-gap="12" :y-gap="12">
          <n-grid-item v-for="preset in showPresets" :key="preset.id">
            <n-card hoverable class="preset-card" @click="openExecuteModal(preset)">
              <template #header>
                <div class="preset-header">
                  <span>{{ preset.name }}</span>
                  <n-tag size="small" type="info">查看</n-tag>
                </div>
              </template>
              <p class="preset-desc">{{ preset.description }}</p>
              <div class="preset-vendors">
                <n-popover trigger="hover">
                  <template #trigger>
                    <span>
                      <n-tag
                        v-for="v in preset.supported_vendors.slice(0, 3)"
                        :key="v"
                        size="tiny"
                        style="margin-right: 4px"
                      >
                        {{ v.toUpperCase() }}
                      </n-tag>
                    </span>
                  </template>
                  支持厂商: {{ preset.supported_vendors.join(', ') }}
                </n-popover>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-card>

      <!-- 配置类操作 -->
      <n-card title="配置类操作" size="small">
        <n-grid :cols="4" :x-gap="12" :y-gap="12">
          <n-grid-item v-for="preset in configPresets" :key="preset.id">
            <n-card hoverable class="preset-card" @click="openExecuteModal(preset)">
              <template #header>
                <div class="preset-header">
                  <span>{{ preset.name }}</span>
                  <n-tag size="small" type="warning">配置</n-tag>
                </div>
              </template>
              <p class="preset-desc">{{ preset.description }}</p>
              <div class="preset-vendors">
                <n-tag
                  v-for="v in preset.supported_vendors.slice(0, 3)"
                  :key="v"
                  size="tiny"
                  style="margin-right: 4px"
                >
                  {{ v.toUpperCase() }}
                </n-tag>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-card>
    </n-spin>

    <!-- 执行弹窗 -->
    <n-modal
      v-model:show="showExecuteModal"
      preset="dialog"
      :title="`执行: ${currentPreset?.name || ''}`"
      style="width: 500px"
    >
      <n-spin :show="deviceLoading">
        <n-form label-placement="left" label-width="100">
          <n-form-item label="目标设备" required>
            <n-select
              v-model:value="selectedDeviceId"
              :options="filteredDeviceOptions"
              placeholder="请选择设备"
              filterable
            />
          </n-form-item>

          <!-- 动态参数表单 -->
          <n-form-item
            v-for="prop in schemaProperties"
            :key="prop.key"
            :label="prop.title"
            :required="prop.required"
          >
            <!-- 数字类型 -->
            <n-input-number
              v-if="prop.type === 'integer' || prop.type === 'number'"
              v-model:value="formParams[prop.key] as number"
              :placeholder="prop.description || `请输入${prop.title}`"
              :min="prop.minimum"
              :max="prop.maximum"
              style="width: 100%"
            />
            <!-- 字符串类型 -->
            <n-input
              v-else
              v-model:value="formParams[prop.key] as string"
              :placeholder="prop.description || `请输入${prop.title}`"
              :maxlength="prop.maxLength"
            />
          </n-form-item>
        </n-form>
      </n-spin>

      <template #action>
        <n-space justify="end">
          <n-button @click="showExecuteModal = false">取消</n-button>
          <n-button
            type="primary"
            :loading="executing"
            :disabled="!selectedDeviceId"
            @click="handleExecute"
          >
            执行
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 结果弹窗 -->
    <n-modal
      v-model:show="showResultModal"
      preset="card"
      title="执行结果"
      style="width: 800px; max-height: 80vh"
    >
      <template v-if="executeResult">
        <n-result
          v-if="!executeResult.success"
          status="error"
          title="执行失败"
          :description="executeResult.error_message || '未知错误'"
        />
        <template v-else>
          <n-tabs v-model:value="resultTab" type="line">
            <n-tab-pane name="raw" tab="原始输出">
              <n-code
                :code="executeResult.raw_output || '(无输出)'"
                language="text"
                style="max-height: 500px; overflow: auto"
              />
            </n-tab-pane>
            <n-tab-pane name="parsed" tab="结构化数据">
              <template v-if="executeResult.parse_error">
                <n-result
                  status="warning"
                  title="解析失败"
                  :description="executeResult.parse_error"
                />
              </template>
              <template v-else-if="executeResult.parsed_output">
                <n-code
                  :code="formattedParsedOutput"
                  language="json"
                  style="max-height: 500px; overflow: auto"
                />
              </template>
              <template v-else>
                <n-result status="info" title="无结构化数据" description="此操作不支持结构化解析" />
              </template>
            </n-tab-pane>
          </n-tabs>
        </template>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.preset-operations {
  padding: 16px;
}

.preset-card {
  cursor: pointer;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.preset-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.preset-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preset-desc {
  margin: 8px 0;
  font-size: 12px;
  color: #999;
  line-height: 1.4;
}

.preset-vendors {
  margin-top: 8px;
}
</style>
