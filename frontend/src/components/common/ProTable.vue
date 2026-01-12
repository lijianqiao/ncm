<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import {
  NDataTable,
  NCard,
  NSpace,
  NButton,
  NInput,
  NSelect,
  NIcon,
  NDropdown,
  type DataTableColumns,
  type PaginationProps,
  type DropdownOption,
} from 'naive-ui'
import {
  SearchOutline as SearchIcon,
  RefreshOutline as RefreshIcon,
  AddOutline as AddIcon,
  TrashOutline as TrashIcon,
  DownloadOutline as DownloadIcon,
} from '@vicons/ionicons5'

// Export this for use in other components
export interface FilterConfig {
  key: string
  label?: string
  placeholder?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  options: { label: string; value: any }[]
  multiple?: boolean
  width?: number
}

// Define props with defaults
const props = withDefaults(
  defineProps<{
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    columns: DataTableColumns<any>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request: (params: any) => Promise<{ data: any[]; total: number }>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rowKey?: (row: any) => string | number
    title?: string
    loading?: boolean
    searchPlaceholder?: string
    searchFilters?: FilterConfig[]
    contextMenuOptions?: DropdownOption[]
    scrollX?: number
    showAdd?: boolean
    showRecycleBin?: boolean
    showBatchDelete?: boolean
    // 虚拟滚动配置（适用于大数据量场景）
    // 虚拟滚动配置（适用于大数据量场景）
    virtualScroll?: boolean
    maxHeight?: number
    // 是否禁用分页（用于树形表格）
    disablePagination?: boolean
  }>(),
  {
    scrollX: 1000,
    title: '',
    searchPlaceholder: '请输入关键字搜索...',
    searchFilters: () => [],
    loading: false,
    contextMenuOptions: () => [],
    showAdd: false,
    showRecycleBin: false,
    disablePagination: false,
    showBatchDelete: false,
    virtualScroll: false,
    maxHeight: 600,
  },
)

const emit = defineEmits<{
  (e: 'update:checked-row-keys', keys: Array<string | number>): void
  (e: 'add'): void
  (e: 'batch-delete', keys: Array<string | number>): void
  (e: 'reset'): void
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (e: 'context-menu-select', key: string | number, row: any): void
  (e: 'recycle-bin'): void
}>()

// State
const tableLoading = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const data = ref<any[]>([])
const checkedRowKeys = ref<Array<string | number>>([])
const keyword = ref('')

// External Filters State (NSelects)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const filterState = ref<Record<string, any>>({})

const handleFilterStateChange = () => {
  // If we want auto-search on select change, uncomment next line:
  // handleSearchClick()
}

const pagination = reactive<PaginationProps>({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix: ({ itemCount }) => `共 ${itemCount} 条`,
  onChange: (page: number) => {
    pagination.page = page
    handleSearch()
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    handleSearch()
  },
})

// 排序状态（远程排序）
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const sorterState = ref<any>(null)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const controlledColumns = ref<any[]>([])

// Initialize columns
onMounted(() => {
  controlledColumns.value = [...props.columns]
  handleSearch()
})

// Watch for column prop changes
import { watch } from 'vue'
watch(
  () => props.columns,
  (newVal) => {
    controlledColumns.value = [...newVal]
  },
  { deep: true },
)

// Filters State (Internal Column Filters - kept for compatibility but effectively replaced by external)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const filters = ref<Record<string, any>>({})

// Helper for deep comparison
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const isDeepEqual = (obj1: any, obj2: any) => {
  return JSON.stringify(obj1) === JSON.stringify(obj2)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handleFiltersChange = (newFilters: Record<string, any>, sourceColumn: any) => {
  // 1. Update Controlled Columns State (UI)
  const columnKey = sourceColumn.key
  const columnIndex = controlledColumns.value.findIndex((col) => col.key === columnKey)
  if (columnIndex !== -1) {
    const filterVal = newFilters[sourceColumn.key]
    if (sourceColumn.filterMultiple) {
      controlledColumns.value[columnIndex].filterOptionValues = filterVal || []
    } else {
      controlledColumns.value[columnIndex].filterOptionValue = filterVal
    }
  }

  // 2. Format Filters for API
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const formattedFilters: Record<string, any> = {}

  Object.keys(newFilters).forEach((key) => {
    const val = newFilters[key]
    const col = controlledColumns.value.find((c) => c.key === key)
    if (col && !col.filterMultiple && Array.isArray(val)) {
      // If single select but got array (Naive UI default), take first.
      formattedFilters[key] = val && val.length ? val[0] : null
    } else {
      formattedFilters[key] = val
    }
  })

  // Prevent redundant search if filters haven't changed
  if (isDeepEqual(filters.value, formattedFilters)) {
    return
  }

  // Filters state update
  filters.value = formattedFilters

  pagination.page = 1
  handleSearch()
}

// Context Menu State
const showDropdown = ref(false)
const uniqueDropdownX = ref(0)
const uniqueDropdownY = ref(0)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const currentRow = ref<any>(null)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const rowProps = (row: any) => {
  return {
    onContextmenu: (e: MouseEvent) => {
      if (!props.contextMenuOptions || props.contextMenuOptions.length === 0) return
      e.preventDefault()
      showDropdown.value = false
      nextTick().then(() => {
        showDropdown.value = true
        uniqueDropdownX.value = e.clientX
        uniqueDropdownY.value = e.clientY
        currentRow.value = row
      })
    },
  }
}

const handleContextMenuSelect = (key: string | number) => {
  showDropdown.value = false
  emit('context-menu-select', key, currentRow.value)
}

const clickOutside = () => {
  showDropdown.value = false
}

// API Request
const handleSearch = async () => {
  tableLoading.value = true
  try {
    // 1. Prepare base params
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters.value, // Internal column filters
      ...filterState.value, // External select filters
    }

    // 3) 排序参数（后端服务端排序）
    if (sorterState.value && sorterState.value.columnKey && sorterState.value.order) {
      params.sort_by = sorterState.value.columnKey
      params.sort_order = sorterState.value.order === 'ascend' ? 'asc' : 'desc'
    }

    // 2. Add keyword only if present and non-empty
    const kw = keyword.value.trim()
    if (kw) {
      params.keyword = kw
    }

    const res = await props.request(params)

    data.value = res.data
    pagination.itemCount = res.total
  } catch (error) {
    console.error('ProTable Request Error:', error)
  } finally {
    tableLoading.value = false
  }
}

const handleRefresh = () => {
  handleSearch()
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handleSorterChange = (sorter: any) => {
  sorterState.value = sorter

  // 同步列 sortOrder，确保 UI 箭头状态正确
  if (sorter && sorter.columnKey) {
    controlledColumns.value = controlledColumns.value.map((col) => {
      if (!col || !col.key) return col
      if (col.key === sorter.columnKey) return { ...col, sortOrder: sorter.order }
      return { ...col, sortOrder: false }
    })
  } else {
    controlledColumns.value = controlledColumns.value.map((col) => {
      if (!col || !col.key) return col
      return { ...col, sortOrder: false }
    })
  }

  pagination.page = 1
  handleSearch()
}

const handleSearchClick = () => {
  pagination.page = 1
  handleSearch()
}

const handleResetClick = () => {
  keyword.value = ''
  // Reset external filters
  filterState.value = {}
  emit('reset')
  pagination.page = 1
  handleSearch()
}

const handleCheck = (keys: Array<string | number>) => {
  checkedRowKeys.value = keys
  emit('update:checked-row-keys', keys)
}

// Export CSV
const handleExport = () => {
  if (!data.value || data.value.length === 0) return

  const headers = props.columns
    .filter((col) => col.type !== 'selection' && col.type !== 'expand' && col.key !== 'actions')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((col: any) => col.title || col.key)

  const keys = props.columns
    .filter((col) => col.type !== 'selection' && col.type !== 'expand' && col.key !== 'actions')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((col: any) => col.key)

  const csvContent = [
    headers.join(','),
    ...data.value.map((row) =>
      keys
        .map((key) => {
          const val = row[key]
          return val === null || val === undefined ? '' : `"${val}"`
        })
        .join(','),
    ),
  ].join('\n')

  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', `${props.title || 'data'}_export.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Expose methods to parent
defineExpose({
  reload: handleSearch,
  refresh: handleSearch,
  reset: handleResetClick,
  getSelectedRows: () =>
    data.value.filter((row) => {
      const key = props.rowKey ? props.rowKey(row) : row.id
      return checkedRowKeys.value.includes(key)
    }),
  getSelectedKeys: () => checkedRowKeys.value,
})
</script>

<template>
  <div class="pro-table" @click="clickOutside">
    <!-- Search Form Area -->
    <n-card class="search-card" :bordered="false" size="small">
      <div class="search-bar">
        <!-- Keyword Search -->
        <n-input
          v-model:value="keyword"
          :placeholder="searchPlaceholder || '请输入关键字搜索...'"
          @keydown.enter.prevent="handleSearchClick"
          class="search-input"
          clearable
        >
          <template #prefix>
            <n-icon><SearchIcon /></n-icon>
          </template>
        </n-input>

        <!-- Dynamic Filters -->
        <template v-for="filter in searchFilters" :key="filter.key">
          <n-select
            v-model:value="filterState[filter.key]"
            :placeholder="filter.placeholder || filter.label"
            :options="filter.options"
            :multiple="filter.multiple"
            :style="{ width: (filter.width || 120) + 'px' }"
            clearable
            @update:value="handleFilterStateChange"
          />
        </template>

        <n-space>
          <n-button type="primary" @click="handleSearchClick">搜索</n-button>
          <n-button @click="handleResetClick">重置</n-button>
        </n-space>

        <div style="margin-left: auto">
          <n-button v-if="showRecycleBin" type="warning" ghost @click="$emit('recycle-bin')">
            <template #icon>
              <n-icon><TrashIcon /></n-icon>
            </template>
            回收站
          </n-button>
        </div>
      </div>
      <!-- Backward compatibility for custom search slot if needed -->
      <div v-if="$slots.search" style="margin-top: 12px">
        <slot name="search"></slot>
      </div>
    </n-card>

    <!-- Toolbar & Table Area -->
    <n-card class="table-card" :bordered="false" size="small">
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="title">{{ title }}</div>
        <n-space>
          <slot name="toolbar-left">
            <n-button
              v-if="checkedRowKeys.length > 0 && showBatchDelete"
              type="error"
              @click="$emit('batch-delete', checkedRowKeys)"
            >
              <template #icon>
                <n-icon><TrashIcon /></n-icon>
              </template>
              批量删除
            </n-button>
          </slot>

          <!-- Create Button (Moved here, before Export) -->
          <n-button v-if="showAdd" type="primary" @click="$emit('add')">
            <template #icon>
              <n-icon><AddIcon /></n-icon>
            </template>
            新建
          </n-button>

          <n-button secondary @click="handleExport" title="导出 CSV">
            <template #icon>
              <n-icon><DownloadIcon /></n-icon>
            </template>
          </n-button>

          <n-button circle secondary @click="handleRefresh" title="刷新">
            <template #icon>
              <n-icon><RefreshIcon /></n-icon>
            </template>
          </n-button>
        </n-space>
      </div>

      <!-- Main Table -->
      <n-data-table
        :remote="true"
        :loading="loading || tableLoading"
        :columns="controlledColumns"
        :data="data"
        :pagination="disablePagination ? false : pagination"
        :row-key="rowKey"
        :row-props="rowProps"
        v-model:checked-row-keys="checkedRowKeys"
        @update:checked-row-keys="handleCheck"
        @update:filters="handleFiltersChange"
        @update:sorter="handleSorterChange"
        :scroll-x="scrollX"
        :virtual-scroll="virtualScroll"
        :max-height="virtualScroll ? maxHeight : undefined"
        flex-height
        style="height: 100%; min-height: 600px; flex: 1"
      />

      <!-- Context Menu -->
      <n-dropdown
        placement="bottom-start"
        trigger="manual"
        :x="uniqueDropdownX"
        :y="uniqueDropdownY"
        :options="contextMenuOptions"
        :show="showDropdown"
        :on-clickoutside="clickOutside"
        @select="handleContextMenuSelect"
      />
    </n-card>
  </div>
</template>

<style scoped>
.pro-table {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.search-card {
  border-radius: 8px;
}

.search-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 300px;
}

.table-card {
  border-radius: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* Fix table height for flex-height */
:deep(.n-card__content) {
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.title {
  font-size: 16px;
  font-weight: 500;
}
</style>
