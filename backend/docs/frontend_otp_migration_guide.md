# 前端 OTP 模块适配指南

> 本文档描述后端 OTP 模块重构后，前端需要进行的适配修改。

## 1. 核心变更概述

### 1.1 字段统一命名

所有 OTP 相关字段已统一添加 `otp_` 前缀：

| 旧字段名 | 新字段名 | 说明 |
|---------|---------|------|
| `credential_id` | `otp_credential_id` | 凭据 ID |
| `credential_username` | `otp_credential_username` | 凭据账号 |
| `credential_device_group` | `otp_credential_device_group` | 凭据分组 |
| `failed_device_ids` | `otp_failed_device_ids` | OTP 失败的设备 ID 列表 |
| `wait_status` | `otp_wait_status` | 等待状态 |

### 1.2 移除的向后兼容字段

以下字段已被移除，请勿再使用：

- `otp_required_groups` → 使用 `otp_credentials`
- `expires_in`（在 428 响应中）→ 使用 `otp_cache_ttl`
- `BackupTaskStatus` 外层的 OTP 字段（见下文）

---

## 2. 备份模块适配

### 2.1 BackupTaskStatus 结构变更

**变更前**：OTP 信息同时存在于 `otp_notice` 和外层字段中

```typescript
// ❌ 旧结构（已废弃）
interface BackupTaskStatus {
  task_id: string;
  status: string;
  // ... 其他字段 ...
  otp_notice: OTPNotice | null;
  
  // 这些外层字段已移除
  otp_required: boolean | null;
  otp_credential_id: string | null;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[] | null;
  otp_wait_status: string | null;
  pending_device_ids: string[] | null;
}
```

**变更后**：OTP 信息**仅通过 `otp_notice` 返回**

```typescript
// ✅ 新结构
interface BackupTaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  progress: object | null;
  
  // 进度数值
  completed: number | null;
  total: number | null;
  percent: number | null;
  
  // 结果摘要
  total_devices: number | null;
  success_count: number | null;
  failed_count: number | null;
  failed_devices: FailedDevice[] | null;
  
  // OTP 信息（唯一来源）
  otp_notice: OTPNotice | null;
}
```

### 2.2 OTPNotice 结构

```typescript
interface OTPNotice {
  type: 'otp_required' | 'otp_timeout';
  message: string;
  otp_credential_id: string | null;        // 注意：使用 otp_ 前缀
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[] | null;
  pending_device_ids: string[] | null;
  task_id: string | null;
  otp_wait_status: 'waiting' | 'timeout' | 'ready' | null;
  otp_wait_timeout: number | null;
  otp_cache_ttl: number | null;
}
```

### 2.3 轮询任务状态代码适配

```typescript
// ❌ 旧代码
async function pollBackupTaskStatus(taskId: string) {
  const response = await api.get(`/backups/task/${taskId}`);
  const status = response.data.data;
  
  // 旧的判断方式（已废弃）
  if (status.otp_required) {
    showOtpDialog({
      credentialId: status.otp_credential_id,
      // ...
    });
  }
}

// ✅ 新代码
async function pollBackupTaskStatus(taskId: string) {
  const response = await api.get(`/backups/task/${taskId}`);
  
  // 检查 428 状态码
  if (response.status === 428) {
    handleOtpRequired(response.data);
    return;
  }
  
  const status: BackupTaskStatus = response.data.data;
  
  // 只检查 otp_notice
  if (status.otp_notice) {
    showOtpDialog({
      credentialId: status.otp_notice.otp_credential_id,
      username: status.otp_notice.otp_credential_username,
      deviceGroup: status.otp_notice.otp_credential_device_group,
      failedDeviceIds: status.otp_notice.otp_failed_device_ids,
      message: status.otp_notice.message,
      waitStatus: status.otp_notice.otp_wait_status,
      waitTimeout: status.otp_notice.otp_wait_timeout,
      cacheTtl: status.otp_notice.otp_cache_ttl,
    });
    return;
  }
  
  // 继续处理正常状态...
  updateProgress(status.percent, status.completed, status.total);
}
```

---

## 3. 428 OTP 响应适配

### 3.1 响应结构

```typescript
interface OtpRequiredResponse {
  code: 428;
  message: string;
  data: {
    otp_required: true;
    otp_credential_id: string;
    otp_credential_username: string | null;
    otp_credential_device_group: string | null;
    otp_failed_device_ids: string[];
    otp_wait_status: 'waiting' | 'timeout' | null;
    otp_wait_timeout: number;
    otp_cache_ttl: number;
    pending_device_ids: string[];
    otp_credentials: OtpCredentialGroup[];  // 凭证列表（唯一字段）
  };
}

interface OtpCredentialGroup {
  otp_credential_id: string;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[];
  pending_device_ids: string[];
  otp_wait_status: string | null;
}
```

### 3.2 处理代码适配

```typescript
// ❌ 旧代码
const credentials = data.otp_credentials || data.otp_required_groups;
const ttl = data.expires_in || data.otp_cache_ttl;

// ✅ 新代码
const credentials = data.otp_credentials;
const ttl = data.otp_cache_ttl;
```

---

## 4. 部署模块适配

### 4.1 DeployTaskResult 结构

```typescript
// ✅ 新结构
interface DeployTaskResult {
  otp_required?: boolean;
  otp_credentials?: OtpCredentialGroup[];  // 唯一字段
  next_action?: 'cache_otp_and_retry_execute' | 'cache_otp_and_retry_rollback';
  otp_wait_status?: string;
  otp_wait_timeout?: number;
  otp_cache_ttl?: number;
  task_id?: string;
}
```

### 4.2 处理代码适配

```typescript
// ❌ 旧代码
if (result.otp_required_groups?.length) {
  // ...
}

// ✅ 新代码
if (result.otp_credentials?.length) {
  showOtpDialog({
    credentials: result.otp_credentials,
    nextAction: result.next_action,
    waitTimeout: result.otp_wait_timeout,
    cacheTtl: result.otp_cache_ttl,
  });
}
```

---

## 5. 拓扑和预设模块

这些模块仍使用扁平的 OTP 字段结构（未使用 `otp_notice`），字段命名已统一：

```typescript
interface TopologyCollectResult {
  // ... 其他字段 ...
  otp_required: boolean;
  otp_credential_id: string | null;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[];
  otp_wait_status: string | null;
  otp_wait_timeout: number | null;
  otp_cache_ttl: number | null;
}

interface PresetExecuteResult {
  // ... 其他字段 ...
  otp_required: boolean;
  otp_credential_id: string | null;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[];
  otp_wait_status: string | null;
  otp_wait_timeout: number | null;
  otp_cache_ttl: number | null;
  next_action: string | null;
}
```

---

## 6. TypeScript 类型定义更新

建议在前端项目中更新以下类型定义文件：

```typescript
// types/otp.ts

/** OTP 通知结构（备份任务状态中使用） */
export interface OTPNotice {
  type: 'otp_required' | 'otp_timeout';
  message: string;
  otp_credential_id: string | null;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[] | null;
  pending_device_ids: string[] | null;
  task_id: string | null;
  otp_wait_status: 'waiting' | 'timeout' | 'ready' | null;
  otp_wait_timeout: number | null;
  otp_cache_ttl: number | null;
}

/** OTP 凭证分组（428 响应中使用） */
export interface OtpCredentialGroup {
  otp_credential_id: string;
  otp_credential_username: string | null;
  otp_credential_device_group: string | null;
  otp_failed_device_ids: string[];
  pending_device_ids: string[];
  otp_wait_status: string | null;
}

/** 备份任务状态 */
export interface BackupTaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  progress: Record<string, unknown> | null;
  completed: number | null;
  total: number | null;
  percent: number | null;
  total_devices: number | null;
  success_count: number | null;
  failed_count: number | null;
  failed_devices: Array<{ name: string; error: string }> | null;
  otp_notice: OTPNotice | null;
}
```

---

## 7. 检查清单

在完成适配后，请确认以下事项：

- [ ] 移除对 `otp_required_groups` 的引用，改用 `otp_credentials`
- [ ] 移除对 428 响应中 `expires_in` 的引用，改用 `otp_cache_ttl`
- [ ] 备份任务状态只通过 `otp_notice` 获取 OTP 信息
- [ ] 所有 OTP 字段使用 `otp_` 前缀（如 `otp_credential_id`）
- [ ] 更新 TypeScript 类型定义
- [ ] 测试 OTP 弹窗显示正确的凭据信息

---

## 8. 常见问题

### Q: 为什么移除外层 OTP 字段？

A: 为了避免数据冗余和不一致。现在 OTP 信息只通过 `otp_notice` 对象返回，前端只需检查一个字段。

### Q: 如何判断是否需要 OTP？

A:

1. **HTTP 428 状态码**：请求被拒绝，需要 OTP
2. **`otp_notice` 不为 null**：轮询时发现需要 OTP

### Q: `otp_credentials` 和 `otp_notice` 的区别？

A:

- `otp_credentials`：在 428 响应中返回，包含所有需要 OTP 的凭证列表
- `otp_notice`：在任务状态轮询时返回，表示当前任务需要 OTP 输入
