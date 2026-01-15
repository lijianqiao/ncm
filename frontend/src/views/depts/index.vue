<script setup lang="ts">
/**
 * @Author: li
 * @Email: lijianqiao2906@live.com
 * @FileName: index.vue
 * @DateTime: 2026-01-08
 * @Docs: 部门管理页面，支持树形结构展示、CRUD、回收站
 */

import { ref, h, computed } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSwitch,
  useDialog,
  type DataTableColumns,
  type FormRules,
  NInputNumber,
  NTreeSelect,
  type DropdownOption,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getDeptTree,
  createDept,
  updateDept,
  deleteDept,
  batchDeleteDepts,
  getRecycleBinDepts,
  restoreDept,
  batchRestoreDepts,
  type Dept,
  type DeptCreate,
  type DeptUpdate,
  type DeptSearchParams,
} from '@/api/depts'
import { formatDateTime } from '@/utils/date'
import ProTable, { type FilterConfig } from '@/components/common/ProTable.vue'

defineOptions({
  name: 'DeptManagement',
})

const dialog = useDialog()
const tableRef = ref()
const recycleBinTableRef = ref()

interface TreeSelectOption {
  label: string
  key: string
  children?: TreeSelectOption[]
}

// 部门树数据（用于选择父部门）
const deptTreeOptions = ref<TreeSelectOption[]>([])

// 回收站选中项
const recycleBinCheckedKeys = ref<string[]>([])
const hasRecycleBinSelection = computed(() => recycleBinCheckedKeys.value.length > 0)

// State
const showCreateModal = ref(false)
const showRecycleBin = ref(false)
const modalType = ref<'create' | 'edit'>('create')
const modalLoading = ref(false)
const formRef = ref()

// Model
const model = ref<DeptCreate & DeptUpdate>({
  name: '',
  code: '',
  parent_id: null,
  sort: 0,
  leader: '',
  phone: '',
  email: '',
  is_active: true,
})

const rules: FormRules = {
  name: { required: true, message: '请输入部门名称', trigger: 'blur' },
  code: { required: true, message: '请输入部门编码', trigger: 'blur' },
  sort: { type: 'number', required: true, message: '请输入排序', trigger: ['blur', 'change'] },
}

// Columns
const columns: DataTableColumns<Dept> = [
  { type: 'selection', fixed: 'left' },
  { title: '部门名称', key: 'name', width: 200, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '编码', key: 'code', width: 150 },
  { title: '排序', key: 'sort', width: 80 },
  { title: '负责人', key: 'leader', width: 120 },
  { title: '联系电话', key: 'phone', width: 150 },
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
    render: (row) => formatDateTime(row.created_at),
  },
]

// Recycle Bin Columns
const recycleBinColumns: DataTableColumns<Dept> = [
  { type: 'selection', fixed: 'left' },
  { title: '部门名称', key: 'name', width: 200 },
  { title: '编码', key: 'code', width: 150 },
  { title: '删除时间', key: 'updated_at', render: (row) => formatDateTime(row.updated_at) },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'success',
          quaternary: true,
          onClick: () => handleRestore(row),
        },
        { default: () => '恢复' },
      )
    },
  },
]

// Context Menu
const contextMenuOptions: DropdownOption[] = [
  { label: '编辑', key: 'edit' },
  { label: '删除', key: 'delete' },
]

const handleContextMenuSelect = (key: string | number, row: Dept) => {
  if (key === 'edit') handleEdit(row)
  if (key === 'delete') handleDelete(row)
}

const recycleBinContextMenuOptions: DropdownOption[] = [{ label: '恢复', key: 'restore' }]
const handleRecycleBinContextMenuSelect = (key: string | number, row: Dept) => {
  if (key === 'restore') handleRestore(row)
}

// Actions
const handleStatusChange = async (row: Dept, value: boolean) => {
  const originalValue = row.is_active
  try {
    row.is_active = value
    await updateDept(row.id, { is_active: value })
    $alert.success(`${value ? '启用' : '停用'}成功`)
  } catch {
    row.is_active = originalValue
    $alert.error('操作失败')
  }
}

const handleCreate = async () => {
  modalType.value = 'create'
  model.value = {
    name: '',
    code: '',
    parent_id: null,
    sort: 0,
    leader: '',
    phone: '',
    email: '',
    is_active: true,
  }
  await fetchDeptTree()
  showCreateModal.value = true
}

const handleEdit = async (row: Dept) => {
  modalType.value = 'edit'
  model.value = {
    ...row,
    // Add id for update request
    // @ts-expect-error id is added for update
    id: row.id,
  }
  await fetchDeptTree()
  showCreateModal.value = true
}

const handleDelete = (row: Dept) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除部门 "${row.name}" 吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteDept(row.id)
        $alert.success('删除成功')
        await tableRef.value?.refresh()
        await fetchDeptTree() // 刷新树数据
      } catch {
        // Error handled
      }
    },
  })
}

const handleBatchDelete = (ids: Array<string | number>) => {
  dialog.warning({
    title: '批量删除',
    content: `确定要删除选中的 ${ids.length} 个部门吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDeleteDepts(ids as string[])
        $alert.success('批量删除成功')
        await tableRef.value?.refresh()
        await fetchDeptTree()
      } catch {
        // Error handled
      }
    },
  })
}

const handleSubmit = async () => {
  const params: Record<string, unknown> = {}
  Object.keys(model.value).forEach((key) => {
    // @ts-expect-error key access
    const value = model.value[key]
    if (value !== null && value !== '' && value !== undefined) {
      params[key] = value
    }
  })

  // 使用 Promise 包装 validate，确保正确的异步处理
  return new Promise<void>((resolve) => {
    formRef.value?.validate(async (errors: unknown) => {
      if (!errors) {
        modalLoading.value = true
        try {
          if (modalType.value === 'create') {
            await createDept(params as unknown as DeptCreate)
            $alert.success('创建成功')
          } else {
            // @ts-expect-error id is added for update
            await updateDept(model.value.id, params as unknown as DeptUpdate)
            $alert.success('更新成功')
          }
          showCreateModal.value = false
          // 先刷新表格数据，再刷新树数据
          await tableRef.value?.refresh()
          await fetchDeptTree()
        } catch {
          // Error handled
        } finally {
          modalLoading.value = false
        }
      }
      resolve()
    })
  })
}

// Recycle Bin Actions
const handleRecycleBin = () => {
  showRecycleBin.value = true
  recycleBinTableRef.value?.refresh()
}

const handleRestore = async (row: Dept) => {
  try {
    await restoreDept(row.id)
    $alert.success('恢复成功')
    recycleBinTableRef.value?.refresh()
    tableRef.value?.refresh()
  } catch {
    // Error handled
  }
}

const handleBatchRestore = async (ids: Array<string | number>) => {
  try {
    await batchRestoreDepts(ids as string[])
    $alert.success('批量恢复成功')
    recycleBinTableRef.value?.refresh()
    tableRef.value?.refresh()
  } catch {
    // Error handled
  }
}

// Data Fetching
const fetchDeptTree = async () => {
  try {
    const res = await getDeptTree()
    // Transform for tree select: id as key, name as label
    const transform = (
      items: Dept[],
    ): { label: string; key: string; children?: { label: string; key: string }[] }[] => {
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

const loadData = async (params: DeptSearchParams) => {
  // 树形结构不支持后端分页和搜索（因为搜索会破坏树结构，除非后端支持返回带搜索结果的树）
  // 这里的 params 包含 keyword, is_active 等
  // 如果是树形展示，通常一次性加载所有数据，然后在前端过滤（也是 Naive UI 的 filter-mode="client" 模式）
  // 或者后端支持树形搜索
  // 调用 getDeptTree，它支持 is_active 过滤
  const isActive = params.is_active
  const res = await getDeptTree(isActive)
  // 如果有关键字，可以在前端做简单的过滤，或者直接返回树
  // 如果需要关键字搜索，可能需要后端支持返回扁平列表然后前端构建树，或者后端直接返回过滤后的树
  // 目前 getDeptTree 只支持 is_active
  return {
    data: res.data || [],
    total: (res.data || []).length, // 树形不分页，total 不重要
  }
}

const recycleBinRequest = async (params: DeptSearchParams) => {
  const res = await getRecycleBinDepts(params)
  return {
    data: res.data.items || [],
    total: res.data.total || 0,
  }
}

// Search Filters
const searchFilters: FilterConfig[] = [
  {
    key: 'is_active',
    label: '状态',
    placeholder: '全部',
    options: [
      { label: '启用', value: true },
      { label: '停用', value: false },
    ],
  },
]

// 注意：不在 onMounted 中调用 fetchDeptTree()
// 因为 ProTable 会在 onMounted 中调用 loadData，两个相似请求会导致第一个被取消
// fetchDeptTree 会在需要时（如打开新建/编辑弹窗）调用
</script>

<template>
  <div class="dept-management p-4">
    <ProTable
      ref="tableRef"
      title="部门管理"
      :columns="columns"
      :request="loadData"
      :row-key="(row) => row.id"
      :context-menu-options="contextMenuOptions"
      search-placeholder="搜索部门名称/编码"
      :search-filters="searchFilters"
      @add="handleCreate"
      @batch-delete="handleBatchDelete"
      @context-menu-select="handleContextMenuSelect"
      @recycle-bin="handleRecycleBin"
      show-add
      show-recycle-bin
      show-batch-delete
      disable-pagination
      :scroll-x="1200"
    />

    <!-- Create/Edit Modal -->
    <NModal
      v-model:show="showCreateModal"
      preset="dialog"
      :title="modalType === 'create' ? '创建部门' : '编辑部门'"
      style="width: 600px"
    >
      <NForm
        ref="formRef"
        :model="model"
        :rules="rules"
        label-placement="left"
        label-width="auto"
        require-mark-placement="right-hanging"
      >
        <NFormItem label="上级部门" path="parent_id">
          <NTreeSelect
            v-model:value="model.parent_id"
            :options="deptTreeOptions"
            placeholder="请选择上级部门（留空为顶级部门）"
            clearable
            key-field="key"
            label-field="label"
          />
        </NFormItem>
        <NFormItem label="部门名称" path="name">
          <NInput v-model:value="model.name" placeholder="请输入部门名称" />
        </NFormItem>
        <NFormItem label="部门编码" path="code">
          <NInput v-model:value="model.code" placeholder="请输入部门编码" />
        </NFormItem>
        <NFormItem label="排序" path="sort">
          <NInputNumber v-model:value="model.sort" :min="0" />
        </NFormItem>
        <NFormItem label="负责人" path="leader">
          <NInput v-model:value="model.leader" placeholder="请输入负责人姓名" />
        </NFormItem>
        <NFormItem label="联系电话" path="phone">
          <NInput v-model:value="model.phone" placeholder="请输入联系电话" />
        </NFormItem>
        <NFormItem label="联系邮箱" path="email">
          <NInput v-model:value="model.email" placeholder="请输入联系邮箱" />
        </NFormItem>
      </NForm>
      <template #action>
        <NButton @click="showCreateModal = false">取消</NButton>
        <NButton type="primary" :loading="modalLoading" @click="handleSubmit">确定</NButton>
      </template>
    </NModal>

    <!-- Recycle Bin Modal -->
    <NModal
      v-model:show="showRecycleBin"
      preset="card"
      title="回收站 (已删除部门)"
      style="width: 800px"
    >
      <ProTable
        ref="recycleBinTableRef"
        :columns="recycleBinColumns"
        :request="recycleBinRequest"
        :row-key="(row) => row.id"
        search-placeholder="搜索已删除部门..."
        :context-menu-options="recycleBinContextMenuOptions"
        @context-menu-select="handleRecycleBinContextMenuSelect"
        @update:checked-row-keys="(keys) => (recycleBinCheckedKeys = keys as string[])"
      >
        <template #toolbar-left>
          <NButton
            v-if="hasRecycleBinSelection"
            type="success"
            @click="handleBatchRestore(recycleBinCheckedKeys)"
          >
            批量恢复 ({{ recycleBinCheckedKeys.length }})
          </NButton>
        </template>
      </ProTable>
    </NModal>
  </div>
</template>

<style scoped>
.dept-management {
  height: 100%;
}
.p-4 {
  padding: 16px;
}
.flex {
  display: flex;
}
.gap-2 {
  gap: 8px;
}
</style>
