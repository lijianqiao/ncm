# NCM 前端

基于 **Vue 3 + Naive UI + TypeScript + Vite** 构建的网络配置管理前端。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3, TypeScript, Vite |
| UI | Naive UI |
| 状态 | Pinia |
| 可视化 | vis-network (拓扑图) |

## 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 设备管理 | `/ncm/devices` | 设备 CRUD、凭据管理、状态监控 |
| 配置备份 | `/ncm/backups` | 手动/批量备份、版本对比 |
| 配置下发 | `/ncm/deploy` | 模板部署、命令预览、执行结果 |
| 资产发现 | `/ncm/discovery` | 网段扫描、CMDB 对账 |
| 拓扑展示 | `/ncm/topology` | 物理拓扑可视化 |
| 告警管理 | `/ncm/alerts` | 告警列表、批量确认 |

## 快速开始

```bash
# 1. 安装依赖
pnpm install

# 2. 配置环境
cp .env.example .env.development

# 3. 启动开发
pnpm dev
```

访问地址: http://127.0.0.1:5173

## 常用命令

| 命令 | 说明 |
|------|------|
| `pnpm dev` | 启动开发服务 |
| `pnpm build` | 生产环境构建 |
| `pnpm lint` | 代码检查 |
| `pnpm type-check` | 类型检查 |

## 目录结构

```
src/
├── api/              # API 接口
├── views/ncm/        # 网络管理页面
├── components/       # 公共组件 (ProTable, OtpModal, UnifiedDiffViewer)
├── composables/      # 组合式函数 (useTaskPolling, useOtpFlow)
├── stores/           # Pinia 状态
└── router/           # 路由配置
```

## License

MIT License
