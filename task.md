# NCM 系统代码审查问题修复计划

根据代码审查报告和上下文信息，制定分阶段修复计划，按优先级处理 P0/P1/P2 级别问题。

## 阶段一：P0 高优先级（立即修复）✅ 已完成

1. ✅ **添加通用异常处理器** - 在 exception_handlers.py 添加 `generic_exception_handler` 捕获所有未处理异常，返回统一错误格式，避免堆栈泄露

2. ✅ **完善数据库连接池配置** - 在 db.py 添加 `pool_recycle=3600` 参数，并在 config.py 添加 `DB_POOL_RECYCLE` 配置项；同时添加 `close_db()` 函数用于应用关闭时清理

3. ✅ **修复 API 路由前缀重复** - 移除 backups.py、discovery.py、collect.py、topology.py、templates.py、render.py、deploy.py 等文件中的重复 prefix 参数

4. ✅ **修复批量删除异常处理** - 在 base.py 的 `batch_remove` 方法中添加日志记录，区分异常类型

5. ✅ **修复前端 Token 刷新失败处理** - 在 request.ts 的 `onTokenRefreshFailed` 中遍历并 reject 所有等待的订阅者

6. ✅ **重构权限指令** - 在 permission.ts 使用 `display: none` 替代 DOM 删除，并添加 `updated` 钩子

7. ✅ **修复路由守卫处理** - 在 router/index.ts logout 后调用 `next({ name: 'Login' })` 而非直接 return

---

## 阶段二：P1 中优先级（近期修复）✅ 已完成

1. ✅ **细化 CORS 配置** - 在 main.py 将 `allow_methods` 限制为 `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]`，`allow_headers` 限制为实际需要的头部

2. ✅ **Celery 任务幂等性保护** - 在 deploy.py 添加 `max_retries=0` 和 `autoretry_for=()` 禁用自动重试

3. ✅ **CSRF Token 全面携带** - 在 request.ts 请求拦截器中为 POST/PUT/DELETE/PATCH 请求自动添加 CSRF Token

4. ✅ **任务轮询超时机制** - 创建 `useTaskPolling` composable，已在 backups/collect/discovery/topology 页面应用（150次×2秒=5分钟超时）

5. ✅ **Redis URL 密码转义** - 在 config.py 的 `REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` 计算属性中使用 `urllib.parse.quote` 转义密码

---

## 阶段三：P2 持续改进（已完成）

1. ✅ **提取分页验证逻辑** - 在 base.py 添加 `_validate_pagination()` 和 `_escape_like()` 静态方法，所有 CRUD 可复用

2. ✅ **前端组件拆分** - 已创建 `DeviceStatistics`、`DeviceStatusTransitionModal` 子组件

3. ✅ **创建 Composables** - 已创建 `useDeptTree`、`useTaskPolling` 组合式函数并导出

4. ✅ **统一枚举定义** - 已统一 API 文件（discovery, templates, backups, alerts, inventory）使用 enums.ts 中的类型定义

5. ✅ **补充数据库索引** - 已创建迁移 63d5490fc309，添加 Backup.status、OperationLog.created_at、LoginLog.created_at 索引

---

## 进一步的考虑

1. **环境变量配置**：`DB_POOL_RECYCLE` 是否需要在 .env.example 中添加？建议添加并设置默认值 3600
答：是

2. **CORS 白名单管理**：生产环境 CORS 白名单应从环境变量读取，是否需要添加 `CORS_ALLOW_METHODS` 和 `CORS_ALLOW_HEADERS` 配置项？
答：环境变量中已经有了

3. **Celery 幂等键方案选择**：使用 Redis 分布式锁 vs 数据库唯一约束 vs 任务状态检查，哪种方案更适合当前架构？
答：这个问题你通过代码看下我们更符合什么方案。我们是内部使用系统。