<script setup lang="ts">
import { ref, h, computed, onMounted } from 'vue'
import {
  NButton,
  NFormItem,
  NInput,
  NModal,
  NSwitch,
  useDialog,
  type DataTableColumns,
  NTag,
  NInputNumber,
  NSelect,
  NTreeSelect,
  NGrid,
  NFormItemGridItem,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getMenus,
  getMenuOptions,
  createMenu,
  updateMenu,
  deleteMenu,
  batchDeleteMenus,
  getRecycleBinMenus,
  restoreMenu,
  batchRestoreMenus,
  type Menu,
  type MenuSearchParams,
} from '@/api/menus'
import { getPermissionDict } from '@/api/permissions'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'MenuManagement',
})

const dialog = useDialog()
// const message = useMessage()
const tableRef = ref()
const recycleBinTableRef = ref()

// Data source for TreeSelect (flattened or tree)
const menuOptions = ref<Menu[]>([])
// Permission dictionary options
const permissionOptions = ref<{ label: string; value: string }[]>([])

const handleStatusChange = async (row: Menu, value: boolean) => {
  const originalValue = row.is_active
  try {
    row.is_active = value
    await updateMenu(row.id, { is_active: value })
    $alert.success(`${value ? '启用' : '停用'}成功`)
  } catch {
    row.is_active = originalValue
    $alert.error('操作失败')
  }
}

const columns: DataTableColumns<Menu> = [
  { title: '标题', key: 'title', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', width: 150, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'type',
    width: 80,
    render(row) {
      const typeMap: Record<string, string> = {
        CATALOG: '目录',
        MENU: '菜单',
        PERMISSION: '权限点',
      }
      return h(
        NTag,
        {
          type: row.type === 'CATALOG' ? 'info' : row.type === 'MENU' ? 'success' : 'warning',
          bordered: false,
        },
        { default: () => typeMap[row.type] || row.type },
      )
    },
  },
  { title: '图标', key: 'icon', width: 150, render: (row) => row.icon || '-' },
  { title: '路径', key: 'path', width: 200, ellipsis: { tooltip: true } },
  { title: '组件', key: 'component', width: 200, ellipsis: { tooltip: true } },
  { title: '权限', key: 'permission', width: 150, ellipsis: { tooltip: true } },
  { title: '排序', key: 'sort', width: 80, sorter: 'default' },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render(row) {
      const isActive = row.is_active
      return h(
        NSwitch,
        {
          value: isActive,
          onUpdateValue: (value) => handleStatusChange(row, value),
        },
        { checked: () => '启用', unchecked: () => '停用' },
      )
    },
  },
  {
    title: '隐藏',
    key: 'is_hidden',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: row.is_hidden ? 'warning' : 'success', bordered: false },
        { default: () => (row.is_hidden ? '隐藏' : '显示') },
      )
    },
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.created_at),
  },
]

// Search Filters
const searchFilters: FilterConfig[] = [
  {
    key: 'is_hidden',
    placeholder: '隐藏',
    options: [
      { label: '显示', value: false },
      { label: '隐藏', value: true },
    ],
    width: 100,
  },
  {
    key: 'is_active',
    placeholder: '状态',
    options: [
      { label: '启用', value: true },
      { label: '停用', value: false },
    ],
    width: 100,
  },
  {
    key: 'type',
    placeholder: '类型',
    options: [
      { label: '目录', value: 'CATALOG' },
      { label: '菜单', value: 'MENU' },
      { label: '权限点', value: 'PERMISSION' },
    ],
    width: 100,
  },
]

// Load Data
const loadData = async (params: MenuSearchParams) => {
  const res = await getMenus(params)

  const data = res.data
  const items = data.items || []
  const total = data.total || 0

  // 总是更新菜单选项以保持同步（只在非搜索时更新，避免搜索结果覆盖完整列表）
  if (!params.keyword) {
    menuOptions.value = items
  }

  return {
    data: items,
    total: total,
  }
}

// Context Menu
const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Menu) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
}

// Create/Edit
const showModal = ref(false)
const modalType = ref<'create' | 'edit'>('create')
const formRef = ref()
const model = ref({
  id: '',
  parent_id: null as string | null,
  title: '',
  name: '',
  path: '',
  component: '' as string | null,
  type: 'MENU' as 'CATALOG' | 'MENU' | 'PERMISSION',
  icon: '' as string | null,
  sort: 0,
  permission: '' as string | null,
  is_hidden: false,
  is_active: true,
})

const rules = computed(() => {
  return {
    title: { required: true, message: '请输入标题', trigger: 'blur' },
    name: { required: true, message: '请输入名称', trigger: 'blur' },
    type: { required: true, message: '请选择类型', trigger: 'blur' },
    permission: {
      required: model.value.type === 'PERMISSION',
      message: '请选择权限标识',
      trigger: ['blur', 'change'],
    },
    path: {
      validator: (rule: unknown, value: string) => {
        if (model.value.type === 'MENU') {
          // If filled, must be valid path
          if (value && !/^(\/[a-zA-Z0-9_\-]+)+$/.test(value)) {
            return new Error('路径必须以/开头，只能包含字母数字下划线连字符')
          }
        }
        return true
      },
      trigger: 'blur',
    },
  }
})

const fetchMenuOptions = async () => {
  try {
    const res = await getMenuOptions()
    menuOptions.value = res.data
  } catch {
    // 错误由 request.ts 统一处理
  }
}

const fetchPermissionOptions = async () => {
  try {
    const res = await getPermissionDict()
    permissionOptions.value = (res.data || []).map((item) => ({
      label: `${item.name} (${item.code})`,
      value: item.code,
    }))
  } catch {
    // 错误由 request.ts 统一处理
  }
}

const handleCreate = async () => {
  modalType.value = 'create'
  model.value = {
    id: '',
    parent_id: null,
    title: '',
    name: '',
    path: '',
    component: '',
    type: 'MENU',
    icon: '',
    sort: 0,
    permission: '',
    is_hidden: false,
    is_active: true,
  }
  showModal.value = true
  await fetchMenuOptions()
}

const handleEdit = async (row: Menu) => {
  modalType.value = 'edit'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const isActive = (row as any).is_active !== undefined ? (row as any).is_active : true
  model.value = {
    id: row.id,
    parent_id: row.parent_id,
    title: row.title,
    name: row.name,
    path: row.path,
    component: row.component || '',
    type: row.type,
    icon: row.icon || '',
    sort: row.sort,
    permission: row.permission || '',
    is_hidden: row.is_hidden,
    is_active: isActive,
  }
  showModal.value = true
  await fetchMenuOptions()
}

const handleSubmit = (e: MouseEvent) => {
  e.preventDefault()
  formRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        const data = { ...model.value }
        if (data.component === '') data.component = null
        if (data.icon === '') data.icon = null
        if (data.permission === '') data.permission = null

        // Clean up fields based on type before submitting to avoid validation errors if backend is strict
        if (data.type === 'CATALOG') {
          data.path = ''
          data.permission = null
        } else if (data.type === 'PERMISSION') {
          data.path = ''
        }
        // MENU can have permission or not, path or not

        if (modalType.value === 'create') {
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { id, ...createData } = data
          await createMenu(createData)
          $alert.success('创建成功')
        } else {
          await updateMenu(data.id, data)
          $alert.success('更新成功')
        }
        showModal.value = false
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    }
  })
}

const handleDelete = (row: Menu) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除菜单 ${row.title} 吗?`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteMenu(row.id)
        $alert.success('删除成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// Recycle Bin
const showRecycleBin = ref(false)
const checkedRecycleBinRowKeys = ref<Array<string | number>>([])

const handleRecycleBin = () => {
  showRecycleBin.value = true
  checkedRecycleBinRowKeys.value = []
}

const recycleBinColumns: DataTableColumns<Menu> = [{ type: 'selection', fixed: 'left' }, ...columns]

const handleBatchRestore = async () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  try {
    await batchRestoreMenus(checkedRecycleBinRowKeys.value as string[])
    $alert.success('批量恢复成功')
    checkedRecycleBinRowKeys.value = []
    recycleBinTableRef.value?.reload()
    tableRef.value?.reload()
  } catch {
    // Error handled
  }
}

const handleBatchHardDelete = () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  dialog.warning({
    title: '批量彻底删除',
    content: `确定要彻底删除选中的 ${checkedRecycleBinRowKeys.value.length} 个菜单吗? 此操作无法恢复!`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteMenus(checkedRecycleBinRowKeys.value as string[], true)
        $alert.success('批量彻底删除成功')
        checkedRecycleBinRowKeys.value = []
        recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}
const recycleBinRequest = async (params: MenuSearchParams) => {
  const res = await getRecycleBinMenus(params)
  // Recycle bin API returns PaginatedResponse
  const data = res.data
  const items = data.items || []
  return {
    data: items,
    total: data.total || 0,
  }
}

const recycleBinContextMenuOptions: DropdownOption[] = [
  { label: '恢复', key: 'restore' },
  { label: '彻底删除', key: 'delete' },
]

const handleRecycleBinContextMenuSelect = async (key: string | number, row: Menu) => {
  if (key === 'restore') {
    try {
      await restoreMenu(row.id)
      $alert.success('恢复成功')
      tableRef.value?.reload()
      recycleBinTableRef.value?.reload()
    } catch {
      // Error handled
    }
  }
  if (key === 'delete') {
    dialog.warning({
      title: '彻底删除',
      content: `确定要彻底删除菜单 ${row.title} 吗? 此操作无法恢复!`,
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await batchDeleteMenus([row.id], true)
          $alert.success('彻底删除成功')
          recycleBinTableRef.value?.reload()
        } catch {
          // Error handled
        }
      },
    })
  }
}

onMounted(() => {
  fetchPermissionOptions()
})
</script>

<template>
  <div class="menu-management p-4">
    <ProTable
      ref="tableRef"
      title="菜单列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Menu) => row.id"
      search-placeholder="搜索标题/名称/路径/权限标识"
      :search-filters="searchFilters"
      default-expand-all
      :context-menu-options="contextMenuOptions"
      @add="handleCreate"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-recycle-bin
      show-batch-delete
      :scroll-x="1800"
    >
      <!-- Removed custom search slot -->
    </ProTable>

    <!-- Recycle Bin Modal -->
    <n-modal
      v-model:show="showRecycleBin"
      preset="card"
      title="回收站 (已删除菜单)"
      style="width: 900px"
    >
      <ProTable
        ref="recycleBinTableRef"
        :columns="recycleBinColumns"
        :request="recycleBinRequest"
        :row-key="(row: Menu) => row.id"
        :context-menu-options="recycleBinContextMenuOptions"
        search-placeholder="搜索删除了的菜单"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        v-model:checked-row-keys="checkedRecycleBinRowKeys"
        :scroll-x="1800"
      >
        <template #toolbar-left>
          <n-space>
            <n-button
              type="success"
              :disabled="checkedRecycleBinRowKeys.length === 0"
              @click="handleBatchRestore"
            >
              批量恢复
            </n-button>
            <n-button
              type="error"
              :disabled="checkedRecycleBinRowKeys.length === 0"
              @click="handleBatchHardDelete"
            >
              批量彻底删除
            </n-button>
          </n-space>
        </template>
      </ProTable>
    </n-modal>

    <!-- Create/Edit Modal -->
    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="modalType === 'create' ? '创建菜单' : '编辑菜单'"
      style="width: 600px"
    >
      <n-form ref="formRef" :model="model" :rules="rules" label-placement="left" label-width="100">
        <n-form-item label="上级菜单" path="parent_id">
          <n-tree-select
            v-model:value="model.parent_id"
            :options="menuOptions"
            key-field="id"
            label-field="title"
            children-field="children"
            placeholder="请选择上级菜单"
            clearable
            filterable
            show-line
            check-strategy="all"
          />
        </n-form-item>
        <n-form-item label="菜单类型" path="type">
          <n-select
            v-model:value="model.type"
            :options="[
              { label: '目录', value: 'CATALOG' },
              { label: '菜单', value: 'MENU' },
              { label: '权限点', value: 'PERMISSION' },
            ]"
          />
        </n-form-item>
        <n-form-item label="标题" path="title">
          <n-input v-model:value="model.title" />
        </n-form-item>
        <n-form-item label="名称 (Name)" path="name">
          <n-input v-model:value="model.name" placeholder="路由名称, 如: MenuManagement" />
        </n-form-item>

        <n-form-item label="路径 (Path)" path="path" v-if="model.type === 'MENU'">
          <n-input v-model:value="model.path" placeholder="/system/users" />
        </n-form-item>

        <n-form-item label="组件路径" path="component" v-if="model.type === 'MENU'">
          <n-input
            v-model:value="model.component"
            placeholder="组件路径, 如: /views/menus/index.vue"
          />
        </n-form-item>

        <n-form-item label="权限标识" path="permission" v-if="model.type !== 'CATALOG'">
          <n-select
            v-model:value="model.permission"
            :options="permissionOptions"
            placeholder="请选择权限标识"
            filterable
            clearable
          />
        </n-form-item>

        <n-form-item label="排序" path="sort">
          <n-input-number v-model:value="model.sort" />
        </n-form-item>
        <n-form-item label="图标" path="icon">
          <n-input v-model:value="model.icon" />
        </n-form-item>

        <n-grid :cols="2" :x-gap="24">
          <n-form-item-grid-item label="隐藏" path="is_hidden">
            <n-switch v-model:value="model.is_hidden" />
          </n-form-item-grid-item>
          <n-form-item-grid-item label="状态" path="is_active">
            <n-switch v-model:value="model.is_active" />
          </n-form-item-grid-item>
        </n-grid>
      </n-form>
      <template #action>
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" @click="handleSubmit">提交</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.p-4 {
  padding: 16px;
  height: 100%;
}
</style>
