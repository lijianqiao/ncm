<script setup lang="ts">
/**
 * @Author: Kiro AI
 * @FileName: RecycleBinModal.vue
 * @DateTime: 2026-01-15
 * @Docs: 通用回收站弹窗组件
 */
import { ref, watch, computed } from 'vue'
import { NModal, NButton, NSpace, useDialog, type DataTableColumns, type DropdownOption } from 'naive-ui'
import ProTable from './ProTable.vue'

// Props 定义
const props = withDefaults(
  defineProps<{
    show: boolean
    title?: string
    width?: string | number
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    columns: DataTableColumns<any>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request: (params: any) => Promise<{ data: any[]; total: number }>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rowKey: (row: any) => string | number
    searchPlaceholder?: string
    scrollX?: number
    /** 是否显示批量恢复按钮，默认 true */
    showBatchRestore?: boolean
    /** 是否显示批量彻底删除按钮，默认 true */
    showBatchHardDelete?: boolean
  }>(),
  {
    title: '回收站',
    width: 900,
    searchPlaceholder: '搜索已删除数据...',
    scrollX: 1200,
    showBatchRestore: true,
    showBatchHardDelete: true,
  },
)

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (e: 'restore', row: any): void
  (e: 'batch-restore', ids: Array<string | number>): void
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (e: 'hard-delete', row: any): void
  (e: 'batch-hard-delete', ids: Array<string | number>): void
  (e: 'refresh'): void
}>()

const dialog = useDialog()
const tableRef = ref()
const checkedRowKeys = ref<Array<string | number>>([])

const resolvedColumns = computed(() => {
  const baseColumns = props.columns as unknown[]
  const hasSelection = baseColumns.some((c) => {
    if (typeof c !== 'object' || c === null) return false
    return (c as { type?: unknown }).type === 'selection'
  })
  if (hasSelection) return props.columns
  return [{ type: 'selection', fixed: 'left' }, ...(props.columns as unknown[])] as typeof props.columns
})

// 监听 show 变化，重置选中状态
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      checkedRowKeys.value = []
    }
  },
)

// 右键菜单选项
const contextMenuOptions: DropdownOption[] = [
  { label: '恢复', key: 'restore' },
  { label: '彻底删除', key: 'hard-delete' },
]

// 右键菜单处理
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handleContextMenuSelect = (key: string | number, row: any) => {
  if (key === 'restore') {
    emit('restore', row)
  } else if (key === 'hard-delete') {
    dialog.warning({
      title: '确认彻底删除',
      content: '彻底删除后数据将无法恢复，确定要继续吗？',
      positiveText: '确认删除',
      negativeText: '取消',
      onPositiveClick: () => {
        emit('hard-delete', row)
      },
    })
  }
}

// 批量恢复
const handleBatchRestore = () => {
  if (checkedRowKeys.value.length === 0) return
  emit('batch-restore', [...checkedRowKeys.value])
}

// 批量彻底删除
const handleBatchHardDelete = () => {
  if (checkedRowKeys.value.length === 0) return
  dialog.warning({
    title: '确认批量彻底删除',
    content: `确定要彻底删除选中的 ${checkedRowKeys.value.length} 条数据吗？此操作不可恢复！`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: () => {
      emit('batch-hard-delete', [...checkedRowKeys.value])
    },
  })
}

// 关闭弹窗
const handleClose = () => {
  emit('update:show', false)
}

// 刷新表格
const reload = () => {
  tableRef.value?.reload()
  checkedRowKeys.value = []
}

// 暴露方法
defineExpose({
  reload,
  getSelectedKeys: () => checkedRowKeys.value,
})
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="title"
    :style="{ width: typeof width === 'number' ? `${width}px` : width }"
    @update:show="handleClose"
  >
    <ProTable
      ref="tableRef"
      :columns="resolvedColumns"
      :request="request"
      :row-key="rowKey"
      :search-placeholder="searchPlaceholder"
      :context-menu-options="contextMenuOptions"
      :scroll-x="scrollX"
      v-model:checked-row-keys="checkedRowKeys"
      @context-menu-select="handleContextMenuSelect"
      :column-configurable="false"
      :density-options="false"
      :fullscreen-enabled="false"
    >
      <template #toolbar-left>
        <n-space>
          <n-button
            v-if="showBatchRestore"
            type="success"
            :disabled="checkedRowKeys.length === 0"
            @click="handleBatchRestore"
          >
            批量恢复
          </n-button>
          <n-button
            v-if="showBatchHardDelete"
            type="error"
            :disabled="checkedRowKeys.length === 0"
            @click="handleBatchHardDelete"
          >
            批量彻底删除
          </n-button>
        </n-space>
      </template>
    </ProTable>
  </n-modal>
</template>
