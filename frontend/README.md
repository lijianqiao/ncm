# NCM 管理后台（前端）

基于 Vue 3 + Naive UI + Vite + Pinia + TypeScript 构建的管理后台前端。

## 主要特性

- **RBAC 权限控制**：基于角色/菜单/按钮的细粒度权限管理
- **动态路由**：根据后端返回的菜单结构动态生成前端路由
- **系统管理**：
  - **用户/角色/菜单**：核心权限模型管理
  - **部门管理**：树形结构展示、层级管理、回收站功能
  - **会话管理**：实时监控在线用户、支持强制下线
  - **操作/登录日志**：全方位审计追踪
- **安全增强**：采用 HttpOnly Cookie + CSRF 认证方案，支持 Token 无感刷新
- **性能优化**：ProTable 组件支持虚拟滚动，Vite 产物分包策略
- **现代化架构**：TypeScript 类型安全，Vite 极速构建

## 快速开始

### 1. 环境准备

- Node.js >= 20
- pnpm

### 2. 安装依赖

```bash
pnpm install
```

### 3. 环境配置

复制 `.env.example` 并按需修改：

- `VITE_API_BASE_URL`：接口基础路径，默认 `/api/v1`
- `VITE_PROXY_TARGET`：开发环境代理目标（后端真实地址），默认 `http://127.0.0.1:8000`

```bash
cp .env.example .env.development
```

Windows PowerShell 可用：

```bash
Copy-Item .env.example .env.development
```

### 4. 启动开发

```bash
pnpm dev
```

启动后默认访问：http://127.0.0.1:5173

## 常用命令

| 命令          | 说明                  |
| ------------- | --------------------- |
| `pnpm dev`    | 启动本地开发服务      |
| `pnpm build`  | 打包构建生产环境      |
| `pnpm lint`   | 代码检查与修复        |
| `pnpm format` | 代码格式化 (Prettier) |

## 联调说明

- 前端默认通过 Vite proxy 转发请求到后端：`VITE_PROXY_TARGET`。
- 后端启动后可访问 Swagger：http://127.0.0.1:8000/docs

## 目录结构

- `src/api`: 后端接口定义
- `src/components`: 公共组件 (ProTable, BaseForm 等)
- `src/layouts`: 布局组件 (Sidebar, Header)
- `src/views`: 页面视图
- `src/stores`: Pinia 状态管理
- `src/router`: 路由配置与守卫
- `src/utils`: 工具函数 (Request, Auth, Date)
