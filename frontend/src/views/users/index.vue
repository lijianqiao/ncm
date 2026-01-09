<script setup lang="ts">
import { ref, h, computed } from 'vue'
import {
  NButton,
  NFormItem,
  NInput,
  NModal,
  NSwitch,
  // useMessage, // Removed
  useDialog,
  type DataTableColumns,
  NTag,
  NSelect,
  NTreeSelect,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getUsers,
  createUser,
  updateUser,
  batchDeleteUsers,
  resetUserPassword,
  getRecycleBinUsers,
  restoreUser,
  batchRestoreUsers,
  getUserRoles,
  updateUserRoles,
  type User,
  type UserSearchParams,
} from '@/api/users'
import { getRoles } from '@/api/roles'
import { getDeptTree, type Dept } from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'UserManagement',
})

const dialog = useDialog()
// ProTable 引用
const tableRef = ref()
const recycleBinTableRef = ref()

interface TreeSelectOption {
  label: string
  key: string
  children?: TreeSelectOption[]
}
const deptTreeOptions = ref<TreeSelectOption[]>([])

const fetchDeptTree = async () => {
  try {
    const res = await getDeptTree()
    const transform = (items: Dept[]): TreeSelectOption[] => {
      return items.map((item) => ({
        label: item.name,
        key: item.id,
        children: item.children && item.children.length ? transform(item.children) : undefined,
      }))
    }
    deptTreeOptions.value = transform(res.data || [])
  } catch {
    // Error handled
  }
}

const handleStatusChange = async (row: User, value: boolean) => {
  const originalValue = row.is_active
  try {
    row.is_active = value // 乐观更新
    await updateUser(row.id, { is_active: value })
    $alert.success(`${value ? '启用' : '停用'}成功`)
  } catch {
    row.is_active = originalValue // 失败时回滚
    $alert.error('操作失败')
  }
}

// Columns Definition
const columns: DataTableColumns<User> = [
  { type: 'selection', fixed: 'left' },
  // ID column removed as requested "except id"
  { title: '用户名', key: 'username', width: 120, fixed: 'left', sorter: 'default' },
  {
    title: '所属部门',
    key: 'dept_name',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.dept_name || '-',
  },
  { title: '昵称', key: 'nickname', width: 120, ellipsis: { tooltip: true } },
  { title: '邮箱', key: 'email', width: 200, ellipsis: { tooltip: true } },
  { title: '手机号', key: 'phone', width: 150 },
  { title: '性别', key: 'gender', width: 80, render: (row) => row.gender || '-' },
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
    title: '超级管理员',
    key: 'is_superuser',
    width: 120,
    render(row) {
      return h(
        NTag,
        { type: row.is_superuser ? 'warning' : 'default', bordered: false },
        { default: () => (row.is_superuser ? '是' : '否') },
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
  {
    key: 'is_superuser',
    placeholder: '超级管理员',
    options: [
      { label: '全部', value: null },
      { label: '是', value: true },
      { label: '否', value: false },
    ],
    width: 120,
  },
]

// Data Request Function for ProTable
const loadData = async (params: UserSearchParams) => {
  // Params includes: page, page_size, keyword, + filters (gender, is_active, etc)
  const res = await getUsers(params)
  return {
    data: res.data.items,
    total: res.data.total,
  }
}

// Context Menu Options
const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '分配角色', key: 'assign_roles' },
  { label: '重置密码', key: 'reset_password' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: User) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
  if (key === 'reset_password') handleResetPassword(row)
  if (key === 'assign_roles') handleAssignRoles(row)
}

// Edit User
const handleEdit = (row: User) => {
  modalType.value = 'edit'
  createModel.value = {
    id: row.id,
    username: row.username,
    password: '',
    email: row.email || '',
    phone: row.phone || '',
    nickname: row.nickname || '',
    gender: row.gender || '保密',
    is_active: row.is_active,
    is_superuser: row.is_superuser,
    dept_id: row.dept_id || null,
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const modalType = ref<'create' | 'edit'>('create')

// Create User
const showCreateModal = ref(false)
const createFormRef = ref()
const createModel = ref({
  id: '',
  username: '',
  password: '',
  email: '',
  phone: '',
  nickname: '',
  gender: '保密',
  is_active: true,
  is_superuser: false,
  dept_id: null as string | null,
})
const createRules = computed(() => {
  const rules = {
    username: { required: true, message: '请输入用户名', trigger: 'blur' },
    phone: { required: true, message: '请输入手机号', trigger: 'blur' },
  }
  if (modalType.value === 'create') {
    ;(rules as Record<string, unknown>).password = {
      required: true,
      message: '请输入密码',
      trigger: 'blur',
    }
  }
  return rules
})

const handleCreate = () => {
  modalType.value = 'create'
  createModel.value = {
    id: '',
    username: '',
    password: '',
    email: '',
    phone: '',
    nickname: '',
    gender: '保密',
    is_active: true,
    is_superuser: false,
    dept_id: null,
  }
  fetchDeptTree()
  showCreateModal.value = true
}

const submitCreate = (e: MouseEvent) => {
  e.preventDefault()
  createFormRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        if (modalType.value === 'create') {
          await createUser(createModel.value)
          $alert.success('用户创建成功')
        } else {
          // We need updateUser API.
          // Assuming it exists or I will add it.
          // For now, let's use a placeholder or check prompts.
          // User asked for "Edit module". I must implement it.
          // I will add `updateUser` to imports in next step.
          await updateUser(createModel.value.id, createModel.value)
          $alert.success('用户更新成功')
        }
        showCreateModal.value = false
        tableRef.value?.reload()
      } catch {
        // Error handled in request interceptor
      }
    }
  })
}

// Reset Password
const showResetPwdModal = ref(false)
const resetPwdModel = ref({ userId: '', newPassword: '' })
const resetPwdFormRef = ref()

const handleResetPassword = (row: User) => {
  resetPwdModel.value = { userId: row.id, newPassword: '' }
  showResetPwdModal.value = true
}

const submitResetPwd = (e: MouseEvent) => {
  e.preventDefault()
  resetPwdFormRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      try {
        await resetUserPassword(resetPwdModel.value.userId, resetPwdModel.value.newPassword)
        $alert.success('密码重置成功')
        showResetPwdModal.value = false
      } catch {
        // Error handled
      }
    }
  })
}

// Delete
const handleDelete = (row: User) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除用户 ${row.username} 吗?`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteUsers([row.id])
        $alert.success('用户已删除')
        tableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

// Delete
const handleBatchDelete = (ids: Array<string | number>) => {
  dialog.warning({
    title: '批量删除',
    content: `确定要删除选中的 ${ids.length} 个用户吗?`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteUsers(ids as string[])
        $alert.success('批量删除成功')
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

const recycleBinColumns: DataTableColumns<User> = columns

const handleBatchRestore = async () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  try {
    await batchRestoreUsers(checkedRecycleBinRowKeys.value as string[])
    $alert.success('批量恢复成功')
    checkedRecycleBinRowKeys.value = []
    recycleBinTableRef.value?.reload()
    tableRef.value?.reload() // Refresh main table too
  } catch {
    // Error handled
  }
}

const handleBatchHardDelete = () => {
  if (checkedRecycleBinRowKeys.value.length === 0) return
  dialog.warning({
    title: '批量彻底删除',
    content: `确定要彻底删除选中的 ${checkedRecycleBinRowKeys.value.length} 个用户吗? 此操作无法恢复!`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteUsers(checkedRecycleBinRowKeys.value as string[], true)
        $alert.success('批量彻底删除成功')
        checkedRecycleBinRowKeys.value = []
        recycleBinTableRef.value?.reload()
      } catch {
        // Error handled
      }
    },
  })
}

const recycleBinRequest = async (params: UserSearchParams) => {
  const res = await getRecycleBinUsers(params)
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

const handleRecycleBinContextMenuSelect = async (key: string | number, row: User) => {
  if (key === 'restore') {
    try {
      await restoreUser(row.id)
      $alert.success('恢复成功')
      tableRef.value?.reload() // Refresh main table
      recycleBinTableRef.value?.reload() // Refresh recycle bin
    } catch {
      // Error handled
    }
  }
  if (key === 'delete') {
    dialog.warning({
      title: '彻底删除',
      content: `确定要彻底删除用户 ${row.username} 吗? 此操作无法恢复!`,
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await batchDeleteUsers([row.id], true)
          $alert.success('彻底删除成功')
          recycleBinTableRef.value?.reload() // Refresh recycle bin
        } catch {
          // Error handled
        }
      },
    })
  }
}

// Assign Roles
const showRoleModal = ref(false)
const roleUserId = ref('')
const roleOptions = ref<{ label: string; value: string }[]>([])
const checkedRoleIds = ref<string[]>([])
const roleLoading = ref(false)

const handleAssignRoles = async (row: User) => {
  roleUserId.value = row.id
  showRoleModal.value = true
  roleLoading.value = true
  checkedRoleIds.value = []

  try {
    // parallel fetch: all roles and user roles
    // Use page_size=100 for roles to get most of them. Ideal is a dedicated 'options' API but getRoles works.
    const [rolesRes, userRolesRes] = await Promise.all([
      getRoles({ page_size: 100 }),
      getUserRoles(row.id),
    ])

    const roles = rolesRes.data.items || []
    roleOptions.value = roles.map((r) => ({ label: r.name, value: r.id }))

    const userRoleData = userRolesRes.data
    if (Array.isArray(userRoleData)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      checkedRoleIds.value = userRoleData.map((r: any) => (typeof r === 'object' ? r.id : r))
    }
  } catch (error: unknown) {
    // 403 错误已由 request.ts 统一处理
    const axiosError = error as { response?: { status?: number } }
    if (axiosError.response?.status !== 403) {
      $alert.error('加载角色数据失败')
    }
  } finally {
    roleLoading.value = false
  }
}

const submitAssignRoles = async () => {
  roleLoading.value = true
  try {
    await updateUserRoles(roleUserId.value, checkedRoleIds.value)
    $alert.success('角色分配成功')
    showRoleModal.value = false
  } catch {
    // 错误已由 request.ts 统一处理
  } finally {
    roleLoading.value = false
  }
}
</script>

<template>
  <div class="user-management p-4">
    <ProTable
      ref="tableRef"
      title="用户列表"
      :columns="columns"
      :request="loadData"
      :row-key="(row: User) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索用户名/昵称/邮箱/手机号/性别"
      :search-filters="searchFilters"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-recycle-bin
      show-batch-delete
      :scroll-x="1500"
    >
      <!-- ... -->
    </ProTable>

    <!-- Recycle Bin Modal -->
    <n-modal
      v-model:show="showRecycleBin"
      preset="card"
      title="回收站 (已删除用户)"
      style="width: 800px"
    >
      <ProTable
        ref="recycleBinTableRef"
        :columns="recycleBinColumns"
        :request="recycleBinRequest"
        :row-key="(row: User) => row.id"
        :search-placeholder="'搜索删除了的用户...'"
        :context-menu-options="recycleBinContextMenuOptions"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        v-model:checked-row-keys="checkedRecycleBinRowKeys"
        :scroll-x="1500"
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
      v-model:show="showCreateModal"
      preset="dialog"
      :title="modalType === 'create' ? '创建用户' : '编辑用户'"
    >
      <n-form
        ref="createFormRef"
        :model="createModel"
        :rules="createRules"
        label-placement="left"
        label-width="auto"
      >
        <n-form-item label="用户名" path="username">
          <n-input v-model:value="createModel.username" :disabled="modalType === 'edit'" />
        </n-form-item>
        <n-form-item label="密码" path="password" v-if="modalType === 'create'">
          <n-input v-model:value="createModel.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="手机号" path="phone">
          <n-input v-model:value="createModel.phone" />
        </n-form-item>
        <n-form-item label="邮箱" path="email">
          <n-input v-model:value="createModel.email" />
        </n-form-item>
        <n-form-item label="昵称" path="nickname">
          <n-input v-model:value="createModel.nickname" />
        </n-form-item>
        <n-form-item label="性别" path="gender">
          <n-select
            v-model:value="createModel.gender"
            :options="[
              { label: '男', value: '男' },
              { label: '女', value: '女' },
              { label: '保密', value: '保密' },
            ]"
          />
        </n-form-item>
        <n-form-item label="所属部门" path="dept_id">
          <n-tree-select
            v-model:value="createModel.dept_id"
            :options="deptTreeOptions"
            placeholder="请选择部门"
            clearable
            key-field="key"
            label-field="label"
          />
        </n-form-item>
        <n-form-item label="状态" path="is_active">
          <n-switch v-model:value="createModel.is_active" />
        </n-form-item>
        <n-form-item label="超级管理员" path="is_superuser">
          <n-switch v-model:value="createModel.is_superuser" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showCreateModal = false">取消</n-button>
        <n-button type="primary" @click="submitCreate">提交</n-button>
      </template>
    </n-modal>

    <!-- Reset Password Modal -->
    <n-modal v-model:show="showResetPwdModal" preset="dialog" title="重置密码">
      <n-form
        ref="resetPwdFormRef"
        :model="resetPwdModel"
        :rules="{ newPassword: { required: true, message: '请输入新密码' } }"
      >
        <n-form-item label="新密码" path="newPassword">
          <n-input
            v-model:value="resetPwdModel.newPassword"
            type="password"
            show-password-on="click"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showResetPwdModal = false">取消</n-button>
        <n-button type="primary" @click="submitResetPwd">提交</n-button>
      </template>
    </n-modal>

    <!-- Assign Roles Modal -->
    <n-modal v-model:show="showRoleModal" preset="dialog" title="分配角色">
      <div v-if="roleLoading" style="padding: 20px; text-align: center">加载中...</div>
      <n-form v-else>
        <n-form-item label="角色选择">
          <n-select
            v-model:value="checkedRoleIds"
            multiple
            :options="roleOptions"
            placeholder="请选择角色"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showRoleModal = false">取消</n-button>
        <n-button type="primary" :loading="roleLoading" @click="submitAssignRoles">保存</n-button>
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
