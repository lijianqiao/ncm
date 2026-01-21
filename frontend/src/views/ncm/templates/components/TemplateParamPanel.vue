<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NButton,
  NSpace,
  NInput,
  NSelect,
  NSwitch,
  NCard,
  NGrid,
  NFormItemGi,
  NDynamicTags,
  NInputNumber,
  NCollapse,
  NCollapseItem,
  NIcon,
  NEmpty,
  NTag,
  useDialog,
} from 'naive-ui'
import { AddOutline, TrashOutline, ArrowUpOutline, ArrowDownOutline } from '@vicons/ionicons5'
import type { TemplateParameterCreate, TemplateParamType } from '@/api/templates'

const props = defineProps<{
  modelValue: TemplateParameterCreate[]
  paramTypes: TemplateParamType[]
}>()

const emit = defineEmits(['update:modelValue'])
const dialog = useDialog()

// 本地可编辑的列表
const localParams = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const expandedKeys = ref<string[]>([])

// 获取类型定义的辅助函数
const getTypeMeta = (typeValue: string) => {
  if (!Array.isArray(props.paramTypes)) return undefined
  return props.paramTypes.find((t) => t.value === typeValue)
}

// 添加参数
const handleAdd = () => {
  const currentLen = localParams.value.length
  const newParam: TemplateParameterCreate = {
    name: `param_${currentLen + 1}`,
    label: '',
    param_type: 'string', // 默认类型
    required: true,
    order: currentLen + 1,
  }

  // 触发更新
  const newList = [...localParams.value, newParam]
  localParams.value = newList

  // 自动展开新项 (新项的索引是 newList.length - 1)
  expandedKeys.value = [String(newList.length - 1)]
}

// 删除参数
const handleDelete = (index: number) => {
  dialog.warning({
    title: '删除参数',
    content: '确定要删除该参数吗？',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      const newList = [...localParams.value]
      newList.splice(index, 1)
      localParams.value = newList
    },
  })
}

// 上移
const handleMoveUp = (index: number) => {
  if (index === 0) return
  const newList = [...localParams.value]
  const prev = newList[index - 1]
  const curr = newList[index]
  if (prev && curr) {
    newList[index] = prev
    newList[index - 1] = curr
    // 更新 order
    newList.forEach((p, i) => (p.order = i + 1))

    // 如果之前是展开的，保持展开
    // 简单做法：清空 expandedKeys 让用户重新点；或者尝试交换 key
    // 这里如果 key 是 index (string)，交换内容后，index 不变，所以视觉上就是内容换了位置
    // 如果 expandedKeys 存的是 index，那么 "0" 展开，交换后还是 "0" 展开（现在是原先的 1），这符合预期

    localParams.value = newList
  }
}

// 下移
const handleMoveDown = (index: number) => {
  if (index === localParams.value.length - 1) return
  const newList = [...localParams.value]
  const curr = newList[index]
  const next = newList[index + 1]
  if (curr && next) {
    newList[index] = next
    newList[index + 1] = curr
    // 更新 order
    newList.forEach((p, i) => (p.order = i + 1))
    localParams.value = newList
  }
}

// 类型变化处理
const handleTypeChange = (element: TemplateParameterCreate, value: string) => {
  element.param_type = value
  const meta = getTypeMeta(value)
  if (meta?.has_options && !element.options) {
    element.options = []
  }
}

// 类型选项
const typeOptions = computed(() => {
  if (!Array.isArray(props.paramTypes)) return []
  return props.paramTypes.map((t) => ({
    label: t.label,
    value: t.value,
  }))
})
</script>

<template>
  <div class="template-param-panel">
    <n-space vertical>
      <div class="panel-header">
        <n-space justify="space-between" align="center">
          <h3>参数定义</h3>
          <n-button size="small" type="primary" dashed @click="handleAdd">
            <template #icon>
              <n-icon>
                <AddOutline />
              </n-icon>
            </template>
            添加参数
          </n-button>
        </n-space>
      </div>

      <n-empty v-if="localParams.length === 0" description="暂无参数，请点击上方按钮添加或从模板内容提取" />

      <n-collapse v-else v-model:expanded-names="expandedKeys">
        <n-collapse-item v-for="(element, index) in localParams" :key="index" :name="String(index)">
          <template #header>
            <n-space align="center">
              <span style="font-weight: bold">{{ element.name }}</span>
              <span style="color: #999" v-if="element.label">({{ element.label }})</span>
              <n-tag size="small" :bordered="false">{{
                getTypeMeta(element.param_type)?.label || element.param_type
                }}</n-tag>
              <n-tag v-if="element.required" type="error" size="small" :bordered="false">必填</n-tag>
            </n-space>
          </template>
          <template #header-extra>
            <n-space>
              <n-button circle size="tiny" :disabled="index === 0" @click.stop="handleMoveUp(index)">
                <template #icon><n-icon>
                    <ArrowUpOutline />
                  </n-icon></template>
              </n-button>
              <n-button circle size="tiny" :disabled="index === localParams.length - 1"
                @click.stop="handleMoveDown(index)">
                <template #icon><n-icon>
                    <ArrowDownOutline />
                  </n-icon></template>
              </n-button>
              <n-button circle size="tiny" type="error" @click.stop="handleDelete(index)">
                <template #icon><n-icon>
                    <TrashOutline />
                  </n-icon></template>
              </n-button>
            </n-space>
          </template>

          <n-card size="small" embedded :bordered="false">
            <n-grid :x-gap="12" :y-gap="8" :cols="2">
              <n-form-item-gi label="变量名 (Name)">
                <n-input v-model:value="element.name" placeholder="唯一标识，如 interface_name" />
              </n-form-item-gi>
              <n-form-item-gi label="显示名 (Label)">
                <n-input v-model:value="element.label" placeholder="用户看到的名称" />
              </n-form-item-gi>
              <n-form-item-gi label="类型">
                <n-select :value="element.param_type" @update:value="(v) => handleTypeChange(element, v)"
                  :options="typeOptions" />
              </n-form-item-gi>
              <n-form-item-gi label="必填">
                <n-switch v-model:value="element.required" />
              </n-form-item-gi>
              <n-form-item-gi label="默认值">
                <n-input v-model:value="element.default_value" placeholder="可选" />
              </n-form-item-gi>
              <n-form-item-gi label="描述">
                <n-input v-model:value="element.description" placeholder="参数说明" />
              </n-form-item-gi>

              <!-- 动态字段：Options -->
              <n-form-item-gi :span="2" label="选项列表" v-if="getTypeMeta(element.param_type)?.has_options">
                <n-dynamic-tags v-model:value="element.options" />
              </n-form-item-gi>

              <!-- 动态字段：Range -->
              <template v-if="getTypeMeta(element.param_type)?.has_range">
                <n-form-item-gi label="最小值">
                  <n-input-number v-model:value="element.min_value" />
                </n-form-item-gi>
                <n-form-item-gi label="最大值">
                  <n-input-number v-model:value="element.max_value" />
                </n-form-item-gi>
              </template>

              <!-- 动态字段：Pattern -->
              <n-form-item-gi :span="2" label="正则校验 (Pattern)" v-if="getTypeMeta(element.param_type)?.has_pattern">
                <n-input v-model:value="element.pattern" placeholder="正则表达式" />
              </n-form-item-gi>
            </n-grid>
          </n-card>
        </n-collapse-item>
      </n-collapse>
    </n-space>
  </div>
</template>

<style scoped>
.panel-header {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}
</style>
