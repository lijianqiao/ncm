---
name: ncm-fullstack
description: |
  NCM 网络配置管理系统全栈开发技能。涵盖 Vue 3 + Naive UI 前端、FastAPI + SQLAlchemy 后端、
  Celery 异步任务、Scrapli 网络自动化。用于开发网络设备管理、配置备份、批量下发、资产发现等功能。
---

# NCM 网络配置管理系统全栈开发技能

## 项目概述

NCM 是一套企业级网络配置管理平台，基于 Vue 3 + FastAPI 构建，专注于网络自动化与配置生命周期管理。

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3, TypeScript, Pinia, Naive UI, Vite, vis-network |
| **后端** | FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, PostgreSQL |
| **网络** | Scrapli (Async), Nornir, SNMP (pysnmp), TextFSM |
| **任务队列** | Celery + Redis, Celery Beat |
| **存储** | PostgreSQL, Redis, MinIO |

## 项目结构

```
ncm/
├── frontend/                    # 前端项目 (Vue 3)
│   ├── src/
│   │   ├── api/                 # API 接口定义 (TypeScript)
│   │   ├── views/               # 页面组件
│   │   │   ├── ncm/             # 网络管理页面
│   │   │   └── ...              # 其他管理页面
│   │   ├── components/common/   # 公共组件 (ProTable, RecycleBinModal)
│   │   ├── composables/         # 组合式函数
│   │   └── stores/              # Pinia 状态管理
│   └── README.md
│
├── backend/                     # 后端项目 (FastAPI)
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API 接口层
│   │   ├── services/            # 业务逻辑层
│   │   ├── crud/                # 数据访问层
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic 模式
│   │   ├── network/             # 网络驱动层
│   │   └── celery/tasks/        # 异步任务
│   └── README.md
│
└── README.md
```

---

## 后端开发规范

### 0. 依赖注入模式 (Dependency Injection)

项目使用 FastAPI 的 `Depends` 实现依赖注入，所有依赖定义在 `app/api/deps.py`：

```python
from typing import Annotated
from fastapi import Depends
from app.api import deps

# 1. 数据库会话依赖
SessionDep = Annotated[AsyncSession, Depends(get_db)]

# 2. 当前用户依赖
CurrentUser = Annotated[User, Depends(get_current_user)]

# 3. CRUD 依赖（单例模式）
def get_device_crud() -> CRUDDevice:
    return device_instance  # 全局单例

DeviceCRUDDep = Annotated[CRUDDevice, Depends(get_device_crud)]

# 4. Service 依赖（组合 CRUD）
def get_device_service(
    db: SessionDep,
    device_crud: Annotated[CRUDDevice, Depends(get_device_crud)],
    credential_crud: Annotated[CRUDCredential, Depends(get_credential_crud)],
) -> DeviceService:
    return DeviceService(db, device_crud, credential_crud)

DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]

# 5. 权限校验依赖
def require_permissions(required_permissions: list[str]):
    async def _checker(request: Request, current_user: CurrentUser) -> User:
        if current_user.is_superuser:
            return current_user
        perms = getattr(request.state, "permissions", set())
        if not set(required_permissions).issubset(perms):
            raise ForbiddenException(message="权限不足")
        return current_user
    return _checker
```

**在 API 端点中使用：**

```python
@router.get("/")
async def read_devices(
    device_service: deps.DeviceServiceDep,  # 自动注入 Service
    current_user: deps.CurrentUser,          # 自动注入当前用户
    _: deps.User = Depends(deps.require_permissions(["device:list"])),  # 权限校验
):
    pass
```

### 1. 数据模型 (Models)

所有模型继承自 `AuditableModel`，自动包含以下字段：

```python
from app.models.base import AuditableModel

class Device(AuditableModel):
    __tablename__ = "devices"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    # ... 其他字段
```

`AuditableModel` 自动提供：
- `id`: UUIDv7 主键
- `created_at`, `updated_at`: 时间戳
- `is_deleted`: 软删除标志
- `is_active`: 激活状态
- `version_id`: 乐观锁版本

### 2. CRUD 层

继承 `CRUDBase` 获得标准 CRUD 操作：

```python
from app.crud.base import CRUDBase
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate

class CRUDDevice(CRUDBase[Device, DeviceCreate, DeviceUpdate]):
    async def get_by_ip(self, db: AsyncSession, ip: str) -> Device | None:
        # 自定义查询方法
        pass

device_crud = CRUDDevice(Device)
```

`CRUDBase` 提供的方法：
- `get`, `get_multi_paginated`, `create`, `update` - 基础 CRUD
- `batch_remove(ids, hard_delete=False)` - 批量删除（支持软/硬删除）
- `batch_restore(ids)` - 批量恢复
- `get_multi_deleted_paginated` - 回收站分页查询

### 3. Service 层

业务逻辑封装在 Service 层，使用 `@transactional()` 装饰器管理事务：

```python
from app.core.decorator import transactional

class DeviceService:
    def __init__(self, db: AsyncSession, device_crud: CRUDDevice):
        self.db = db
        self.device_crud = device_crud

    @transactional()
    async def create_device(self, obj_in: DeviceCreate) -> Device:
        # 业务校验
        if await self.device_crud.exists_ip(self.db, obj_in.ip_address):
            raise BadRequestException(message=f"IP 地址 {obj_in.ip_address} 已存在")
        # 创建设备
        return await self.device_crud.create(self.db, obj_in=obj_in)
```

### 4. API 端点

使用 FastAPI 路由，遵循 RESTful 规范：

```python
from fastapi import APIRouter, Depends, Query
from app.api import deps

router = APIRouter()

@router.get("/", response_model=ResponseBase[PaginatedResponse[DeviceResponse]])
async def read_devices(
    device_service: deps.DeviceServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DEVICE_LIST.value])),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str | None = Query(None),
) -> ResponseBase[PaginatedResponse[DeviceResponse]]:
    devices, total = await device_service.get_devices_paginated(query)
    return ResponseBase(data=PaginatedResponse(items=devices, total=total))

# 批量删除
@router.delete("/batch", response_model=ResponseBase[DeviceBatchResult])
async def batch_delete_devices(obj_in: DeviceBatchDeleteRequest, ...):
    result = await device_service.batch_delete_devices(obj_in.ids)
    return ResponseBase(data=result)

# 回收站
@router.get("/recycle-bin", response_model=ResponseBase[PaginatedResponse[DeviceResponse]])
async def read_recycle_bin(...):
    pass

# 恢复
@router.post("/{device_id}/restore")
async def restore_device(...):
    pass

# 批量恢复
@router.post("/batch/restore")
async def batch_restore_devices(...):
    pass

# 彻底删除
@router.delete("/{device_id}/hard")
async def hard_delete_device(...):
    pass

# 批量彻底删除
@router.delete("/batch/hard")
async def batch_hard_delete_devices(...):
    pass
```

### 5. Pydantic Schemas

```python
from pydantic import BaseModel, Field

class DeviceBase(BaseModel):
    name: str = Field(..., max_length=100)
    ip_address: str

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    name: str | None = None
    ip_address: str | None = None

class DeviceResponse(DeviceBase):
    id: str
    created_at: datetime
    is_deleted: bool
    
    model_config = ConfigDict(from_attributes=True)

class DeviceBatchDeleteRequest(BaseModel):
    ids: list[UUID]

class DeviceBatchResult(BaseModel):
    success_count: int
    failed_count: int
    failed_items: list[dict] = []
```

### 6. 通用 Schema (common.py)

项目提供标准化的通用 Schema：

```python
from app.schemas.common import (
    ResponseBase,           # 统一响应格式
    PaginatedResponse,      # 分页响应
    BatchDeleteRequest,     # 批量删除请求
    BatchRestoreRequest,    # 批量恢复请求
    BatchOperationResult,   # 批量操作结果
    TimestampSchema,        # 时间戳混入
)

# 统一响应格式
class ResponseBase[T](BaseModel):
    code: int = 200
    message: str = "Success"
    data: T | None = None

# 分页响应
class PaginatedResponse[T](BaseModel):
    total: int
    page: int
    page_size: int
    items: list[T]

# 批量删除请求
class BatchDeleteRequest(BaseModel):
    ids: list[UUID]
    hard_delete: bool = False  # 默认软删除

# 批量操作结果
class BatchOperationResult(BaseModel):
    success_count: int
    failed_ids: list[UUID] = []
    message: str = "操作完成"
```

### 7. 异常处理 (exceptions.py)

项目定义了标准化的业务异常：

```python
from app.core.exceptions import (
    CustomException,        # 基础异常类
    NotFoundException,      # 404 资源不存在
    ForbiddenException,     # 403 禁止访问
    UnauthorizedException,  # 401 未授权
    BadRequestException,    # 400 无效请求
    DomainValidationException,  # 422 验证错误
)

# 使用示例
from app.core.exceptions import BadRequestException, NotFoundException

async def create_device(self, obj_in: DeviceCreate) -> Device:
    if await self.device_crud.exists_ip(self.db, obj_in.ip_address):
        raise BadRequestException(message=f"IP 地址 {obj_in.ip_address} 已存在")
    return await self.device_crud.create(self.db, obj_in=obj_in)

async def get_device(self, device_id: UUID) -> Device:
    device = await self.device_crud.get(self.db, id=device_id)
    if not device:
        raise NotFoundException(message="设备不存在")
    return device
```

**NCM 特定异常：**

```python
from app.core.exceptions import (
    OTPRequiredException,              # 428 需要 OTP 验证码
    DeviceCredentialNotFoundException,  # 404 设备凭据未找到
)

# OTP 异常（支持断点续传）
raise OTPRequiredException(
    dept_id=dept_id,
    device_group="network",
    failed_devices=["192.168.1.1"],
    message="需要输入 OTP 验证码"
)
```

### 8. 网络自动化

使用 Scrapli Async 进行设备连接：

```python
from app.network.platform_config import get_command, get_scrapli_options
from app.network.async_tasks import async_send_command, async_collect_config

# 获取平台命令
command = get_command("backup_config", "hp_comware")  # display current-configuration

# 异步执行命令
result = await async_send_command(host, command)
```

支持的平台：
- `hp_comware` (H3C)
- `huawei_vrp`
- `cisco_iosxe`, `cisco_nxos`

### 9. Celery 异步任务

```python
from app.celery.app import celery_app
from app.celery.base import BaseTask, run_async

@celery_app.task(base=BaseTask, bind=True, queue="backup")
def backup_devices(self, hosts_data: list[dict], num_workers: int = 50):
    self.update_state(state="PROGRESS", meta={"stage": "executing"})
    # 执行备份逻辑
    run_async(_save_backup_results(hosts_data, summary))
    return summary
```

---

## 前端开发规范

### 1. API 接口定义

```typescript
// frontend/src/api/devices.ts
import { request } from '@/utils/request'
import type { ResponseBase, PaginatedResponse } from '@/types/api'

export interface Device {
  id: string
  name: string
  ip_address: string
  is_deleted: boolean
}

export interface DeviceSearchParams {
  page?: number
  page_size?: number
  keyword?: string
}

// 获取列表
export const getDevices = (params: DeviceSearchParams) =>
  request<ResponseBase<PaginatedResponse<Device>>>({ url: '/devices/', method: 'get', params })

// 批量删除
export const batchDeleteDevices = (ids: string[]) =>
  request<ResponseBase<DeviceBatchResult>>({ url: '/devices/batch', method: 'delete', data: { ids } })

// 回收站
export const getRecycleBinDevices = (params: DeviceSearchParams) =>
  request<ResponseBase<PaginatedResponse<Device>>>({ url: '/devices/recycle-bin', method: 'get', params })

// 恢复
export const restoreDevice = (id: string) =>
  request<ResponseBase<Device>>({ url: `/devices/${id}/restore`, method: 'post' })

// 批量恢复
export const batchRestoreDevices = (ids: string[]) =>
  request<ResponseBase<DeviceBatchResult>>({ url: '/devices/batch/restore', method: 'post', data: { ids } })

// 彻底删除
export const hardDeleteDevice = (id: string) =>
  request<ResponseBase<Record<string, unknown>>>({ url: `/devices/${id}/hard`, method: 'delete' })

// 批量彻底删除
export const batchHardDeleteDevices = (ids: string[]) =>
  request<ResponseBase<DeviceBatchResult>>({ url: '/devices/batch/hard', method: 'delete', data: { ids } })
```

### 2. ProTable 组件使用

`ProTable` 是项目的核心表格组件，封装了 Naive UI 的 `NDataTable`，提供企业级表格功能。

**Props 配置：**

| Prop | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `columns` | `DataTableColumns` | - | 列定义（必填） |
| `request` | `(params) => Promise<{data, total}>` | - | 数据请求函数（必填） |
| `rowKey` | `(row) => string \| number` | - | 行唯一标识 |
| `title` | `string` | `''` | 表格标题 |
| `searchPlaceholder` | `string` | `'请输入关键字搜索...'` | 搜索框占位符 |
| `searchFilters` | `FilterConfig[]` | `[]` | 下拉筛选配置 |
| `contextMenuOptions` | `DropdownOption[]` | `[]` | 右键菜单选项 |
| `scrollX` | `number` | `1000` | 横向滚动宽度 |
| `showAdd` | `boolean` | `false` | 显示新建按钮 |
| `showBatchDelete` | `boolean` | `false` | 显示批量删除按钮 |
| `showRecycleBin` | `boolean` | `false` | 显示回收站按钮 |
| `resizable` | `boolean` | `true` | 列宽可拖拽调整 |
| `columnConfigurable` | `boolean` | `true` | 显示列配置面板 |
| `densityOptions` | `boolean` | `true` | 显示密度切换 |
| `fullscreenEnabled` | `boolean` | `true` | 启用全屏模式 |
| `storageKey` | `string` | - | localStorage 持久化 key |
| `multipleSort` | `boolean` | `false` | 启用多列排序 |
| `virtualScroll` | `boolean` | `false` | 启用虚拟滚动 |
| `maxHeight` | `number` | `600` | 虚拟滚动最大高度 |
| `disablePagination` | `boolean` | `false` | 禁用分页 |

**Exposed 方法：**

```typescript
const tableRef = ref()

// 重新加载数据（保持当前页）
tableRef.value?.reload()

// 刷新（同 reload）
tableRef.value?.refresh()

// 重置搜索条件并刷新
tableRef.value?.reset()

// 重置列配置为默认
tableRef.value?.resetColumnConfig()

// 切换全屏
tableRef.value?.toggleFullscreen()

// 获取选中的行数据
const selectedRows = tableRef.value?.getSelectedRows()

// 获取选中的行 keys
const selectedKeys = tableRef.value?.getSelectedKeys()
```

**Slots：**

- `toolbar-left`: 工具栏左侧自定义内容（批量操作按钮区域）
- `search`: 搜索区域下方自定义内容

**Events：**

| Event | 参数 | 说明 |
|-------|------|------|
| `update:checked-row-keys` | `keys: Array<string \| number>` | 选中行变化 |
| `add` | - | 点击新建按钮 |
| `batch-delete` | `keys: Array<string \| number>` | 点击批量删除 |
| `recycle-bin` | - | 点击回收站按钮 |
| `context-menu-select` | `key: string, row: any` | 右键菜单选择 |
| `reset` | - | 重置搜索条件 |
| `request-error` | `error: unknown` | 请求错误 |

**完整使用示例：**

```vue
<template>
  <ProTable
    ref="tableRef"
    title="设备列表"
    :columns="columns"
    :request="loadData"
    :row-key="(row: Device) => row.id"
    :context-menu-options="contextMenuOptions"
    search-placeholder="搜索设备名称/IP"
    :search-filters="searchFilters"
    v-model:checked-row-keys="selectedRowKeys"
    storage-key="device-table"
    @add="handleCreate"
    @context-menu-select="handleContextMenuSelect"
    show-add
    show-batch-delete
    show-recycle-bin
    @batch-delete="handleBatchDelete"
    @recycle-bin="showRecycleBin = true"
    :scroll-x="1200"
  />
</template>

<script setup lang="ts">
import type { FilterConfig } from '@/components/common/ProTable.vue'

const tableRef = ref()
const selectedRowKeys = ref<string[]>()

// 下拉筛选配置
const searchFilters: FilterConfig[] = [
  {
    key: 'status',
    placeholder: '状态',
    options: [
      { label: '在线', value: 'online' },
      { label: '离线', value: 'offline' },
    ],
    width: 120,
  },
]

const loadData = async (params: DeviceSearchParams) => {
  const res = await getDevices(params)
  return { data: res.data.items, total: res.data.total }
}
</script>
```

### 3. RecycleBinModal 组件使用

```vue
<template>
  <RecycleBinModal
    ref="recycleBinRef"
    v-model:show="showRecycleBin"
    title="回收站 (已删除设备)"
    :columns="recycleBinColumns"
    :request="loadRecycleBinData"
    :row-key="(row: Device) => row.id"
    search-placeholder="搜索已删除设备..."
    :scroll-x="900"
    @restore="handleRestore"
    @batch-restore="handleBatchRestore"
    @hard-delete="handleHardDelete"
    @batch-hard-delete="handleBatchHardDelete"
  />
</template>

<script setup lang="ts">
import RecycleBinModal from '@/components/common/RecycleBinModal.vue'

const showRecycleBin = ref(false)
const recycleBinRef = ref()

const recycleBinColumns: DataTableColumns<Device> = [
  { type: 'selection', fixed: 'left' },
  { title: '名称', key: 'name', width: 150 },
  { title: '删除时间', key: 'updated_at', width: 180 },
]

const loadRecycleBinData = async (params) => {
  const res = await getRecycleBinDevices(params)
  return { data: res.data.items, total: res.data.total }
}

const handleRestore = async (row: Device) => {
  await restoreDevice(row.id)
  $alert.success('已恢复')
  recycleBinRef.value?.reload()
  tableRef.value?.reload()
}

const handleBatchRestore = async (ids: string[]) => {
  await batchRestoreDevices(ids)
  $alert.success('批量恢复成功')
  recycleBinRef.value?.reload()
  tableRef.value?.reload()
}

const handleHardDelete = async (row: Device) => {
  await hardDeleteDevice(row.id)
  $alert.success('已彻底删除')
  recycleBinRef.value?.reload()
}

const handleBatchHardDelete = async (ids: string[]) => {
  await batchHardDeleteDevices(ids)
  $alert.success('批量彻底删除成功')
  recycleBinRef.value?.reload()
}
</script>
```

### 4. 任务轮询 Composable

```typescript
import { useTaskPolling } from '@/composables/useTaskPolling'

const { taskStatus, isPolling, start, stop } = useTaskPolling(
  (taskId) => getBackupTaskStatus(taskId),
  {
    interval: 2000,
    onComplete: (status) => {
      if (status.status === 'SUCCESS') {
        $alert.success('任务完成')
        tableRef.value?.reload()
      }
    },
    onError: (error) => {
      $alert.error(error.message)
    },
  }
)

// 开始轮询
start(taskId)
```

### 5. 请求封装 (request.ts)

项目使用 Axios 封装，支持 HttpOnly Cookie + CSRF 认证方案：

**核心功能：**
- Access Token 存储在内存（非 localStorage，更安全）
- Refresh Token 存储在 HttpOnly Cookie
- 自动 Token 刷新（401 时自动刷新并重试）
- 并发请求时的 Token 刷新队列
- 请求取消管理
- CSRF Token 自动附加

**Token 管理：**

```typescript
import { getAccessToken, setAccessToken, clearAccessToken } from '@/utils/request'

// 登录成功后设置 Token
setAccessToken(response.data.access_token)

// 登出时清除 Token
clearAccessToken()
```

**请求取消：**

```typescript
import { cancelAllRequests, cancelRequest } from '@/utils/request'

// 取消所有待处理请求（如页面切换时）
cancelAllRequests()

// 取消特定请求
cancelRequest('get', '/devices/')
```

**响应拦截器行为：**
- `401`: 自动刷新 Token 并重试原请求
- `403`: 显示 "权限不足" 警告
- `4xx/5xx`: 显示错误消息

### 6. Alert 工具 (alert.ts)

项目使用 `$alert` 全局工具显示消息提示：

```typescript
import { $alert } from '@/utils/alert'

// 成功提示
$alert.success('操作成功')

// 错误提示
$alert.error('操作失败')

// 警告提示
$alert.warning('权限不足')

// 信息提示
$alert.info('提示信息')
```

### 7. Naive UI 组件注意事项

**Drawer 组件**：如果使用 `n-drawer-content`，`n-drawer` 的 `native-scrollbar` 必须设为 `true`：

```vue
<n-drawer v-model:show="showDrawer" :native-scrollbar="true">
  <n-drawer-content title="详情">
    <!-- 内容 -->
  </n-drawer-content>
</n-drawer>
```

**Dialog 确认**：

```typescript
const dialog = useDialog()

dialog.warning({
  title: '确认删除',
  content: '确定要删除吗？',
  positiveText: '确认',
  negativeText: '取消',
  onPositiveClick: async () => {
    await deleteItem(id)
    $alert.success('删除成功')
  },
})
```

---

## 标准功能清单

每个 ProTable 页面应具备：

1. **行选择** - checkbox 列
2. **批量删除** - 工具栏按钮 + `show-batch-delete` prop
3. **回收站** - RecycleBinModal 组件 + `show-recycle-bin` prop
4. **右键菜单** - 查看、编辑、删除等操作
5. **搜索筛选** - 关键字搜索 + 下拉筛选

---

## 常用命令

```bash
# 后端
cd backend
uv run start.py              # 启动 API 服务
uv run start_worker.py       # 启动 Celery Worker
uv run alembic upgrade head  # 数据库迁移
uv run alembic revision --autogenerate -m "描述"  # 生成迁移

# 前端
cd frontend
pnpm dev                     # 启动开发服务
pnpm build                   # 构建生产版本
pnpm lint                    # 代码检查
```

---

## 文件命名规范

- 后端：snake_case（如 `device_service.py`）
- 前端组件：PascalCase（如 `ProTable.vue`）
- 前端 API/工具：camelCase 或 snake_case（如 `devices.ts`）
- API 路由：kebab-case（如 `/batch-delete`, `/recycle-bin`）
```

---
