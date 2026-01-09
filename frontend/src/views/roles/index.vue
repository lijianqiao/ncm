<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NButton,
  NFormItem,
  NInput,
  NModal,
  NSwitch,
  // useMessage, // Removed
  useDialog,
  type DataTableColumns,
  NTree,
  type TreeOption,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  batchDeleteRoles,
  getRecycleBinRoles,
  restoreRole,
  batchRestoreRoles,
  getRoleMenus,
  updateRoleMenus,
  type Role,
  type RoleSearchParams,
} from '@/api/roles'
import { formatDateTime } from '@/utils/date'
import { getMenuOptions, type Menu } from '@/api/menus'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'RoleManagement',
})

const dialog = useDialog()
// const message = useMessage()
const tableRef = ref()
const recycleBinTableRef = ref()

const handleStatusChange = async (row: Role, value: boolean) => {
  const originalValue = row.is_active
  try {
    row.is_active = value
    await updateRole(row.id, { is_active: value })
    $alert.success(`${value ? '启用' : '停用'}成功`)
  } catch {
    row.is_active = originalValue
    $alert.error('操作失败')
  }
}

// Columns
const columns: DataTableColumns<Role> = [
  { type: 'selection', fixed: 'left' },
  { title: '角色名称', key: 'name', width: 150, fixed: 'left', sorter: 'default' },
  { title: '角色标识', key: 'code', width: 150, fixed: 'left', sorter: 'default' },
  { title: '描述', key: 'description', width: 200, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render(row) {
      return h(
        NSwitch,
        {
          value: row.is_active,
          onUpdateValue: (value) => handleStatusChange(row, value),
        },
        { checked: () => '启用', unchecked: () => '停用' },
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
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    sorter: 'default',
    render: (row) => formatDateTime(row.updated_at),
  },
]

// Search Filters
const searchFilters: FilterConfig[] = [
  {
    key: 'is_active',
    placeholder: '状态',
    options: [
      { label: '启用', value: true },
      { label: '停用', value: false },
    ],
    width: 100,
  },
]

// Load Data
const loadData = async (params: RoleSearchParams) => {
  const res = await getRoles(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// Context Menu
const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '权限', key: 'permissions' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Role) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'permissions') handlePermissions(row)
  if (key === 'delete') handleDelete(row)
}

// Create/Edit Role
const showModal = ref(false)
const modalType = ref<'create' | 'edit'>('create')
const formRef = ref()
const model = ref({
  id: '',
  name: '',
  code: '',
  description: '',
  is_active: true,
})
const rules = {
  name: { required: true, message: '请输入角色名称', trigger: 'blur' },
  code: { required: true, message: '请输入角色标识', trigger: 'blur' },
}

const handleCreate = () => {
  modalType.value = 'create'
  model.value = {
    id: '',
    name: '',
    code: '',
    description: '',
    is_active: true,
  }
  showModal.value = true
}

const handleEdit = (row: Role) => {
  modalType.value = 'edit'
  model.value = {
    id: row.id,
    name: row.name,
    code: row.code,
    description: row.description || '',
    is_active: row.is_active,
  }
  showModal.value = true
}

const handleSubmit = (e: MouseEvent) => {
  e.preventDefault()
  formRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        if (modalType.value === 'create') {
          await createRole(model.value)
          $alert.success('创建成功')
        } else {
          await updateRole(model.value.id, model.value)
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

// Delete
const handleDelete = (row: Role) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除角色 ${row.name} 吗?`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteRole(row.id)
        $alert.success('删除成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchDelete = (ids: Array<string | number>) => {
  dialog.warning({
    title: '批量删除',
    content: `确定要删除选中的 ${ids.length} 个角色吗?`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await Promise.all(ids.map((id) => deleteRole(id as string)))
        $alert.success('批量删除成功')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// Permissions
const showPermModal = ref(false)
const permRoleId = ref('')
const permTreeData = ref<TreeOption[]>([])
const checkedKeys = ref<string[]>([])
const permLoading = ref(false)
const permPattern = ref('')

// Filter function for Tree Search
const filterPermTree = (pattern: string, option: TreeOption): boolean => {
  if (option.label && typeof option.label === 'string') {
    return option.label.toLowerCase().includes(pattern.toLowerCase())
  }
  return false
}

// Helper to convert Menu[] to TreeOption[]
const mapMenusToOptions = (menus: Menu[]): TreeOption[] => {
  return menus.map((menu) => ({
    key: menu.id,
    label: menu.title,
    children: menu.children ? mapMenusToOptions(menu.children) : undefined,
  }))
}

const handlePermissions = async (row: Role) => {
  permRoleId.value = row.id
  showPermModal.value = true
  permLoading.value = true
  checkedKeys.value = []
  try {
    const [menusRes, roleMenusRes] = await Promise.all([getMenuOptions(), getRoleMenus(row.id)])
    const menuItems = menusRes.data || []
    permTreeData.value = mapMenusToOptions(menuItems)

    const roleMenuData = roleMenusRes.data
    // Assuming API returns string[] or { menu_ids: string[] }
    // Based on api.md, it returns 'array' (likely string[] since we defined it as such in api/roles.ts)
    if (Array.isArray(roleMenuData)) {
      checkedKeys.value = roleMenuData
    } else {
      checkedKeys.value = []
    }
  } catch (error: unknown) {
    // 403 错误已由 request.ts 统一处理
    const axiosError = error as { response?: { status?: number } }
    if (axiosError.response?.status !== 403) {
      $alert.error('加载权限数据失败')
    }
  } finally {
    permLoading.value = false
  }
}

const submitPermissions = async () => {
  permLoading.value = true
  try {
    await updateRoleMenus(permRoleId.value, checkedKeys.value)
    $alert.success('权限分配成功')
    showPermModal.value = false
  } catch {
    // Error handled
  } finally {
    permLoading.value = false
  }
}

// Recycle Bin
const showRecycleBin = ref(false)
const checkedRecycleBinRowKeys = ref<Array<string | number>>([])

const handleRecycleBin = () => {
  showRecycleBin.value = true
  checkedRecycleBinRowKeys.value = []
}

const recycleBinColumns: DataTableColumns<Role> = columns

const handleBatchRestore = async () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  try {
    await batchRestoreRoles(checkedRecycleBinRowKeys.value as string[])
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
    content: `确定要彻底删除选中的 ${checkedRecycleBinRowKeys.value.length} 个角色吗? 此操作无法恢复!`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteRoles(checkedRecycleBinRowKeys.value as string[], true)
        $alert.success('批量彻底删除成功')
        checkedRecycleBinRowKeys.value = []
        recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const recycleBinRequest = async (params: RoleSearchParams) => {
  const res = await getRecycleBinRoles(params)
  const data = res.data
  return {
    data: data.items,
    total: data.total,
  }
}

const recycleBinContextMenuOptions: DropdownOption[] = [
  { label: '恢复', key: 'restore' },
  { label: '彻底删除', key: 'delete' },
]

const handleRecycleBinContextMenuSelect = async (key: string | number, row: Role) => {
  if (key === 'restore') {
    try {
      await restoreRole(row.id)
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
      content: `确定要彻底删除角色 ${row.name} 吗? 此操作无法恢复!`,
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await batchDeleteRoles([row.id], true)
          $alert.success('彻底删除成功')
          recycleBinTableRef.value?.reload()
        } catch {
          // Error handled
        }
      },
    })
  }
}
</script>

<template>
  <div class="role-management p-4">
    <ProTable
      ref="tableRef"
      title="角色列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: Role) => row.id"
      search-placeholder="搜索角色名称/角色标识/描述"
      :search-filters="searchFilters"
      :context-menu-options="contextMenuOptions"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-recycle-bin
      show-batch-delete
      :scroll-x="1200"
    >
      <!-- Removed custom search slot -->
    </ProTable>

    <!-- Recycle Bin Modal -->
    <n-modal
      v-model:show="showRecycleBin"
      preset="card"
      title="回收站 (已删除角色)"
      style="width: 800px"
    >
      <ProTable
        ref="recycleBinTableRef"
        :columns="recycleBinColumns"
        :request="recycleBinRequest"
        :row-key="(row: Role) => row.id"
        search-placeholder="搜索删除了的角色"
        :context-menu-options="recycleBinContextMenuOptions"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        v-model:checked-row-keys="checkedRecycleBinRowKeys"
        :scroll-x="1200"
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
      :title="modalType === 'create' ? '创建角色' : '编辑角色'"
    >
      <n-form ref="formRef" :model="model" :rules="rules" label-placement="left" label-width="auto">
        <n-form-item label="角色名称" path="name">
          <n-input v-model:value="model.name" />
        </n-form-item>
        <n-form-item label="角色标识" path="code">
          <n-input v-model:value="model.code" />
        </n-form-item>
        <n-form-item label="描述" path="description">
          <n-input v-model:value="model.description" type="textarea" />
        </n-form-item>
        <n-form-item label="状态" path="is_active">
          <n-switch v-model:value="model.is_active" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showModal = false">取消</n-button>
        <n-button type="primary" @click="handleSubmit">提交</n-button>
      </template>
    </n-modal>

    <!-- Permissions Modal -->
    <n-modal v-model:show="showPermModal" preset="dialog" title="分配菜单权限">
      <div style="max-height: 400px; overflow: auto">
        <n-input
          v-model:value="permPattern"
          placeholder="搜索菜单权限..."
          style="margin-bottom: 8px"
        />
        <n-tree
          block-line
          cascade
          checkable
          show-line
          expand-on-pattern-match
          :data="permTreeData"
          :checked-keys="checkedKeys"
          :pattern="permPattern"
          :filter="filterPermTree"
          @update:checked-keys="(keys) => (checkedKeys = keys)"
        />
      </div>
      <template #action>
        <n-button @click="showPermModal = false">取消</n-button>
        <n-button type="primary" :loading="permLoading" @click="submitPermissions">保存</n-button>
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
