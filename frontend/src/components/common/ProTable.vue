<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, computed, watch, h } from 'vue'
import {
  NDataTable,
  NCard,
  NSpace,
  NButton,
  NInput,
  NSelect,
  NIcon,
  NDropdown,
  NPopover,
  NCheckbox,
  NDivider,
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
  SettingsOutline as SettingsIcon,
  ExpandOutline as ExpandIcon,
  ContractOutline as ContractIcon,
  ReorderFourOutline as DensityIcon,
  ReloadOutline as ResetIcon,
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

// 列配置接口
export interface ColumnConfig {
  key: string
  title: string
  visible: boolean
  order: number
}

// 密度类型
export type TableDensity = 'compact' | 'default' | 'loose'

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
    showExport?: boolean
    virtualScroll?: boolean
    maxHeight?: number
    disablePagination?: boolean
    // 新增功能 props
    resizable?: boolean
    columnConfigurable?: boolean
    densityOptions?: boolean
    fullscreenEnabled?: boolean
    storageKey?: string
    /** 是否启用多列排序，默认 false */
    multipleSort?: boolean
    /** 是否显示搜索栏，默认 true */
    showSearch?: boolean
    /** 是否显示刷新按钮，默认 true */
    showRefresh?: boolean
    /** 表格最小高度，默认 600 */
    minHeight?: number
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
    showExport: false,
    virtualScroll: false,
    maxHeight: 600,
    resizable: true,
    columnConfigurable: true,
    densityOptions: true,
    fullscreenEnabled: true,
    multipleSort: false,
    showSearch: true,
    showRefresh: true,
    minHeight: 600,
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
  (e: 'request-error', error: unknown): void
}>()

// State
const tableLoading = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const data = ref<any[]>([])
const checkedRowKeys = ref<Array<string | number>>([])
const keyword = ref('')

// External Filters State
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const filterState = ref<Record<string, any>>({})

const handleFilterStateChange = () => {
  // Auto-search on filter change (optional)
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

// 排序状态
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const sorterState = ref<any>(null)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const controlledColumns = ref<any[]>([])

const autoScrollX = computed(() => {
  let columnsWidth = 0
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  controlledColumns.value.forEach((col: any) => {
    if (col.type === 'selection') {
      columnsWidth += 50
    } else if (typeof col.width === 'number') {
      columnsWidth += col.width
    } else {
      columnsWidth += 150 // 默认估算宽度
    }
  })
  // 确保不小于传入的 scrollX，也不小于计算出的总宽
  return Math.max(columnsWidth, props.scrollX || 1000)
})

// ==================== 列配置功能 ====================
const columnConfig = ref<ColumnConfig[]>([])
const showColumnConfig = ref(false)

// 初始化列配置
const initColumnConfig = () => {
  // 尝试从 localStorage 加载
  if (props.storageKey) {
    const saved = localStorage.getItem(`pro-table-columns-${props.storageKey}`)
    if (saved) {
      try {
        columnConfig.value = JSON.parse(saved)
        return
      } catch {
        // 解析失败，使用默认配置
      }
    }
  }

  // 默认配置：所有列可见
  columnConfig.value = props.columns
    .filter((col) => {
      if (col.type === 'selection') return false
      const key = (col as unknown as { key?: unknown }).key
      return typeof key === 'string' && key.length > 0
    })
    .map((col, index) => {
      const key = (col as unknown as { key: string }).key
      const titleValue = (col as unknown as { title?: unknown }).title
      const title = typeof titleValue === 'string' && titleValue ? titleValue : key
      return { key, title, visible: true, order: index }
    })
}

// 保存列配置到 localStorage
const saveColumnConfig = () => {
  if (props.storageKey) {
    localStorage.setItem(
      `pro-table-columns-${props.storageKey}`,
      JSON.stringify(columnConfig.value),
    )
  }
}

// 切换列可见性
const toggleColumnVisibility = (key: string) => {
  const config = columnConfig.value.find((c) => c.key === key)
  if (config) {
    config.visible = !config.visible
    saveColumnConfig()
    updateDisplayColumns()
  }
}

// 重置列配置
const resetColumnConfig = () => {
  columnConfig.value = props.columns
    .filter((col) => {
      if (col.type === 'selection') return false
      const key = (col as unknown as { key?: unknown }).key
      return typeof key === 'string' && key.length > 0
    })
    .map((col, index) => {
      const key = (col as unknown as { key: string }).key
      const titleValue = (col as unknown as { title?: unknown }).title
      const title = typeof titleValue === 'string' && titleValue ? titleValue : key
      return { key, title, visible: true, order: index }
    })
  saveColumnConfig()
  updateDisplayColumns()
}

// 根据配置更新显示的列
const updateDisplayColumns = () => {
  const baseColumns = [...props.columns] as unknown[]
  const needsSelection = props.showBatchDelete === true
  const hasSelection = baseColumns.some((c) => {
    if (typeof c !== 'object' || c === null) return false
    return (c as { type?: unknown }).type === 'selection'
  })
  const sourceColumns =
    needsSelection && !hasSelection
      ? ([{ type: 'selection', fixed: 'left' }, ...baseColumns] as unknown[])
      : baseColumns

  const visibleKeys = new Set(columnConfig.value.filter((c) => c.visible).map((c) => c.key))

  // 保留 selection 列和可见的列，并自动添加 resizable 属性
  controlledColumns.value = (sourceColumns as typeof props.columns)
    .filter((col) => {
      if (col.type === 'selection') return true
      const key = (col as unknown as { key?: unknown }).key
      return typeof key === 'string' && visibleKeys.has(key)
    })
    .map((col) => {
      if (!props.resizable || col.type === 'selection') return col
      return { ...col, resizable: true }
    })
}

// ==================== 密度切换功能 ====================
const tableDensity = ref<TableDensity>('default')

const densityMenuOptions: DropdownOption[] = [
  { label: '紧凑', key: 'compact', icon: () => h(DensityIcon) },
  { label: '默认', key: 'default', icon: () => h(DensityIcon) },
  { label: '宽松', key: 'loose', icon: () => h(DensityIcon) },
]

const handleDensityChange = (key: string | number) => {
  tableDensity.value = key as TableDensity
  // 保存到 localStorage
  if (props.storageKey) {
    localStorage.setItem(`pro-table-density-${props.storageKey}`, key as string)
  }
}

const loadDensityConfig = () => {
  if (props.storageKey) {
    const saved = localStorage.getItem(`pro-table-density-${props.storageKey}`)
    if (saved && ['compact', 'default', 'loose'].includes(saved)) {
      tableDensity.value = saved as TableDensity
    }
  }
}

// 密度对应的 size
const tableSize = computed(() => {
  const sizeMap: Record<TableDensity, 'small' | 'medium' | 'large'> = {
    compact: 'small',
    default: 'medium',
    loose: 'large',
  }
  return sizeMap[tableDensity.value]
})

// ==================== 全屏功能 ====================
const isFullscreen = ref(false)

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

// ESC 键退出全屏
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  initColumnConfig()
  loadDensityConfig()
  updateDisplayColumns()
  handleSearch()
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

// Watch for column prop changes
watch(
  () => props.columns,
  () => {
    initColumnConfig()
    updateDisplayColumns()
  },
  { deep: true },
)

watch(
  () => props.showBatchDelete,
  () => {
    updateDisplayColumns()
  },
)

// Filters State
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const filters = ref<Record<string, any>>({})

const normalizeComparable = (value: unknown) => {
  if (Array.isArray(value)) return [...value].sort()
  return value
}

const isComparableEqual = (a: unknown, b: unknown) => {
  const na = normalizeComparable(a)
  const nb = normalizeComparable(b)

  if (Array.isArray(na) && Array.isArray(nb)) {
    if (na.length !== nb.length) return false
    for (let i = 0; i < na.length; i++) {
      if (na[i] !== nb[i]) return false
    }
    return true
  }

  return na === nb
}

const isFilterObjectEqual = (a: Record<string, unknown>, b: Record<string, unknown>) => {
  const aKeys = Object.keys(a).sort()
  const bKeys = Object.keys(b).sort()
  if (aKeys.length !== bKeys.length) return false
  for (let i = 0; i < aKeys.length; i++) {
    const key = aKeys[i]
    if (!key) return false
    if (key !== bKeys[i]) return false
    if (!isComparableEqual(a[key], b[key])) return false
  }
  return true
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handleFiltersChange = (newFilters: Record<string, any>, sourceColumn: any) => {
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const formattedFilters: Record<string, any> = {}

  Object.keys(newFilters).forEach((key) => {
    const val = newFilters[key]
    const col = controlledColumns.value.find((c) => c.key === key)
    if (col && !col.filterMultiple && Array.isArray(val)) {
      formattedFilters[key] = val && val.length ? val[0] : null
    } else {
      formattedFilters[key] = val
    }
  })

  if (isFilterObjectEqual(filters.value, formattedFilters)) {
    return
  }

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
const handleSearch = async (silent = false) => {
  if (!silent) {
    tableLoading.value = true
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters.value,
      ...filterState.value,
    }

    // 支持多列排序
    if (Array.isArray(sorterState.value) && sorterState.value.length > 0) {
      // 多列排序：传递数组格式
      const validSorters = sorterState.value.filter(
        (s: { columnKey: string; order: string | false }) => s.columnKey && s.order,
      )
      if (validSorters.length > 0) {
        params.sort_by = validSorters.map((s: { columnKey: string }) => s.columnKey).join(',')
        params.sort_order = validSorters
          .map((s: { order: string }) => (s.order === 'ascend' ? 'asc' : 'desc'))
          .join(',')
      }
    } else if (sorterState.value && sorterState.value.columnKey && sorterState.value.order) {
      // 单列排序
      params.sort_by = sorterState.value.columnKey
      params.sort_order = sorterState.value.order === 'ascend' ? 'asc' : 'desc'
    }

    const kw = keyword.value.trim()
    if (kw) {
      params.keyword = kw
    }

    const res = await props.request(params)

    data.value = res.data
    pagination.itemCount = res.total
  } catch (error: unknown) {
    emit('request-error', error)
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

  // 支持多列排序：sorter 可能是数组或单个对象
  if (Array.isArray(sorter)) {
    // 多列排序
    const sorterMap = new Map(
      sorter.map((s: { columnKey: string; order: string | false }) => [s.columnKey, s.order]),
    )
    controlledColumns.value = controlledColumns.value.map((col) => {
      if (!col || !col.key) return col
      const order = sorterMap.get(col.key)
      return { ...col, sortOrder: order || false }
    })
  } else if (sorter && sorter.columnKey) {
    // 单列排序
    controlledColumns.value = controlledColumns.value.map((col) => {
      if (!col || !col.key) return col
      if (col.key === sorter.columnKey) return { ...col, sortOrder: sorter.order }
      return { ...col, sortOrder: false }
    })
  } else {
    // 清除排序
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

  const escapeCsvValue = (value: unknown) => {
    if (value === null || value === undefined) return '""'
    const str = String(value)
    const escaped = str.replace(/"/g, '""')
    return `"${escaped}"`
  }

  const headers = props.columns
    .filter((col) => col.type !== 'selection' && col.type !== 'expand' && col.key !== 'actions')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((col: any) => col.title || col.key)

  const keys = props.columns
    .filter((col) => col.type !== 'selection' && col.type !== 'expand' && col.key !== 'actions')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((col: any) => col.key)

  const csvContent = [
    headers.map(escapeCsvValue).join(','),
    ...data.value.map((row) =>
      keys
        .map((key) => {
          return escapeCsvValue(row[key])
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
  resetColumnConfig,
  toggleFullscreen,
  getSelectedRows: () =>
    data.value.filter((row) => {
      const key = props.rowKey ? props.rowKey(row) : row.id
      return checkedRowKeys.value.includes(key)
    }),
  getSelectedKeys: () => checkedRowKeys.value,
})
</script>

<template>
  <div class="pro-table" :class="{ 'pro-table--fullscreen': isFullscreen }" @click="clickOutside">
    <!-- Search Form Area -->
    <n-card v-if="showSearch" class="search-card" :bordered="false" size="small">
      <div class="search-bar">
        <!-- Keyword Search -->
        <n-input v-model:value="keyword" :placeholder="searchPlaceholder || '请输入关键字搜索...'"
          @keydown.enter.prevent="handleSearchClick" class="search-input" clearable>
          <template #prefix>
            <n-icon>
              <SearchIcon />
            </n-icon>
          </template>
        </n-input>

        <!-- Dynamic Filters -->
        <template v-for="filter in searchFilters" :key="filter.key">
          <n-select v-model:value="filterState[filter.key]" :placeholder="filter.placeholder || filter.label"
            :options="filter.options" :multiple="filter.multiple" :style="{ width: (filter.width || 120) + 'px' }"
            clearable @update:value="handleFilterStateChange" />
        </template>

        <n-space>
          <n-button type="primary" @click="handleSearchClick">搜索</n-button>
          <n-button @click="handleResetClick">重置</n-button>
        </n-space>

        <div style="margin-left: auto; display: flex; align-items: center; gap: 12px">
          <slot name="search-right"></slot>
          <n-button v-if="showRecycleBin" type="warning" ghost @click="$emit('recycle-bin')">
            <template #icon>
              <n-icon>
                <TrashIcon />
              </n-icon>
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
          <slot name="toolbar-left"></slot>

          <n-button v-if="checkedRowKeys.length > 0 && showBatchDelete" type="error"
            @click="$emit('batch-delete', checkedRowKeys)">
            <template #icon>
              <n-icon>
                <TrashIcon />
              </n-icon>
            </template>
            批量删除
          </n-button>

          <slot name="toolbar"></slot>

          <!-- Create Button -->
          <n-button v-if="showAdd" type="primary" @click="$emit('add')">
            <template #icon>
              <n-icon>
                <AddIcon />
              </n-icon>
            </template>
            新建
          </n-button>

          <!-- Export Button -->
          <n-button v-if="showExport" circle secondary @click="handleExport" title="导出 CSV">
            <template #icon>
              <n-icon>
                <DownloadIcon />
              </n-icon>
            </template>
          </n-button>

          <!-- Density Dropdown -->
          <n-dropdown v-if="densityOptions" trigger="click" :options="densityMenuOptions" @select="handleDensityChange">
            <n-button circle secondary title="表格密度">
              <template #icon>
                <n-icon>
                  <DensityIcon />
                </n-icon>
              </template>
            </n-button>
          </n-dropdown>

          <!-- Column Config Popover -->
          <n-popover v-if="columnConfigurable" trigger="click" placement="bottom-end" :show="showColumnConfig"
            @update:show="showColumnConfig = $event">
            <template #trigger>
              <n-button circle secondary title="列设置">
                <template #icon>
                  <n-icon>
                    <SettingsIcon />
                  </n-icon>
                </template>
              </n-button>
            </template>
            <div class="column-config-panel">
              <div class="column-config-header">
                <span>列设置</span>
                <n-button text size="small" @click="resetColumnConfig">
                  <template #icon>
                    <n-icon size="14">
                      <ResetIcon />
                    </n-icon>
                  </template>
                  重置
                </n-button>
              </div>
              <n-divider style="margin: 8px 0" />
              <div class="column-config-list">
                <div v-for="col in columnConfig" :key="col.key" class="column-config-item">
                  <n-checkbox :checked="col.visible" @update:checked="toggleColumnVisibility(col.key)">
                    {{ col.title }}
                  </n-checkbox>
                </div>
              </div>
            </div>
          </n-popover>

          <!-- Fullscreen Toggle -->
          <n-button v-if="fullscreenEnabled" circle secondary @click="toggleFullscreen"
            :title="isFullscreen ? '退出全屏' : '全屏'">
            <template #icon>
              <n-icon>
                <ContractIcon v-if="isFullscreen" />
                <ExpandIcon v-else />
              </n-icon>
            </template>
          </n-button>

          <!-- Refresh Button -->
          <n-button v-if="showRefresh" circle secondary @click="handleRefresh" title="刷新"
            :loading="loading || tableLoading">
            <template #icon>
              <n-icon>
                <RefreshIcon />
              </n-icon>
            </template>
          </n-button>
        </n-space>
      </div>

      <!-- Main Table -->
      <div class="table-wrap">
        <n-data-table :remote="true" :loading="loading || tableLoading" :columns="controlledColumns" :data="data"
          :pagination="disablePagination ? false : pagination" :row-key="rowKey" :row-props="rowProps" :size="tableSize"
          :resizable="resizable" :multiple="multipleSort" v-model:checked-row-keys="checkedRowKeys"
          @update:checked-row-keys="handleCheck" @update:filters="handleFiltersChange"
          @update:sorter="handleSorterChange" :scroll-x="autoScrollX" :virtual-scroll="virtualScroll"
          :max-height="virtualScroll ? maxHeight : undefined" flex-height
          :style="{ height: '100%', minHeight: minHeight + 'px', flex: 1, minWidth: 0 }" />
      </div>

      <!-- Context Menu -->
      <n-dropdown placement="bottom-start" trigger="manual" :x="uniqueDropdownX" :y="uniqueDropdownY"
        :options="contextMenuOptions" :show="showDropdown" :on-clickoutside="clickOutside"
        @select="handleContextMenuSelect" />
    </n-card>
  </div>
</template>

<style scoped>
.pro-table {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-width: 0;
}

.pro-table--fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background: var(--n-color, #fff);
  padding: 16px;
  overflow: auto;
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
  min-width: 0;
  overflow: hidden;
}

/* Fix table height for flex-height */
:deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  min-width: 0;
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

/* Column Config Panel */
.column-config-panel {
  width: 200px;
}

.column-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.column-config-list {
  max-height: 300px;
  overflow-y: auto;
}

.column-config-item {
  padding: 4px 0;
}

.table-wrap {
  flex: 1;
  min-width: 0;
}
</style>
