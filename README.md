# NCM 网络配置管理系统

**NCM (Network Configuration Management)** 是一套基于 **Vue 3 + FastAPI** 构建的企业级网络配置管理平台，专注于网络自动化与配置生命周期管理，同时内置完整的 RBAC 权限控制与后台管理能力。

## 🌟 网络自动化亮点

| 功能模块     | 描述                                                           |
| ------------ | -------------------------------------------------------------- |
| **配置备份** | 多厂商设备（Cisco/Huawei/H3C）配置自动采集、版本管理、差异对比 |
| **批量下发** | 支持模板变量、OTP 动态密码、断点续传、命令回显审计             |
| **资产发现** | 基于 SNMP/SSH 的网段扫描、设备指纹识别、CMDB 自动对账          |
| **拓扑发现** | LLDP/CDP 邻居采集，自动构建物理拓扑，可视化展示                |
| **告警管理** | 配置变更告警、设备离线检测、Webhook 通知                       |
| **异步架构** | Celery + Scrapli Async，支持 100+ 设备并行采集                 |

## ✨ 核心特性

### 🕸️ 网络自动化

- **多厂商支持**：Cisco IOS/NX-OS/IOS-XR、Huawei VRP、H3C Comware
- **统一平台配置**：`platform_config.py` 集中管理命令映射、Scrapli 参数
- **OTP 动态认证**：支持设备级 OTP 动态密码，按部门/设备组缓存
- **配置差异对比**：基于 MD5 的变更检测，自动生成 Unified Diff
- **定时任务**：Celery Beat 调度配置备份、巡检、扫描任务

### 🛡️ 基础权限

- **RBAC 权限控制**：用户 - 角色 - 菜单/权限 三级权限模型
- **动态路由**：根据用户权限动态生成前端路由和菜单
- **软删除与回收站**：支持数据软删除及恢复
- **审计日志**：自动记录登录日志和操作日志
- **部门管理**：树形结构展示、层级管理

### 🔒 安全特性

- **JWT 双 Token**：Access Token (短期) + Refresh Token (HttpOnly Cookie)
- **CSRF 防护**：双提交 Cookie 模式
- **密码安全**：Argon2/Bcrypt 加密，可配置复杂度要求
- **限流保护**：登录接口限流 (5次/分钟)

## 🛠️ 技术栈

| 层级         | 技术                                                     |
| ------------ | -------------------------------------------------------- |
| **前端**     | Vue 3, TypeScript, Pinia, Naive UI, Vite, vis-network    |
| **后端**     | FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, PostgreSQL |
| **网络**     | Scrapli (Async), Nornir, SNMP (pysnmp), TextFSM          |
| **任务队列** | Celery + Redis, Celery Beat                              |
| **存储**     | PostgreSQL, Redis, MinIO (大配置文件)                    |
| **日志**     | Structlog (JSON 格式)                                    |

## 📂 项目结构

```
ncm/
├── frontend/              # 前端项目 (Vue 3)
│   ├── src/
│   │   ├── api/           # API 接口定义
│   │   ├── views/ncm/     # 网络管理页面 (设备/备份/拓扑/告警)
│   │   ├── components/    # 公共组件 (ProTable, OtpModal)
│   │   └── composables/   # 组合式函数 (useTaskPolling)
│   └── README.md
│
├── backend/               # 后端项目 (FastAPI)
│   ├── app/
│   │   ├── api/v1/        # REST API 接口层
│   │   ├── network/       # 网络驱动层 (Scrapli/Nornir 封装)
│   │   ├── celery/tasks/  # 异步任务 (备份/发现/部署)
│   │   ├── services/      # 业务逻辑层
│   │   └── models/        # SQLAlchemy 模型
│   └── README.md
│
└── README.md              # 本文件
```

## 🚀 快速开始

### 环境要求

- Node.js >= 20
- Python >= 3.13
- PostgreSQL >= 16
- Redis >= 6

### 1. 后端启动

```bash
cd backend

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env

# 生成数据库迁移文件
uv run alembic revision --autogenerate -m "Initial migration"

# 数据库迁移
uv run alembic upgrade head

# 初始化管理员账号
uv run initial_data.py --init

# 启动 API 服务
uv run start.py

# 启动 Celery Worker（网络任务处理）
uv run start_worker.py
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖
pnpm install

# 配置环境变量
cp .env.example .env.development

# 启动开发服务
pnpm dev
```

### 3. 默认账号

| 用户名 | 密码   | 角色       |
| ------ | ------ | ---------- |
| admin  | 123123 | 超级管理员 |

> ⚠️ 生产环境请务必修改默认密码！

## 📋 功能模块

| 模块         | 功能                              |
| ------------ | --------------------------------- |
| **设备管理** | 网络设备 CRUD、凭据管理、状态监控 |
| **配置备份** | 手动/定时备份、版本对比、差异告警 |
| **配置下发** | 批量部署、命令抽屉、执行结果回放  |
| **资产发现** | 网段扫描、SNMP 采集、CMDB 对账    |
| **拓扑发现** | LLDP 邻居采集、物理拓扑可视化     |
| **告警管理** | 配置变更告警、离线检测、批量确认  |
| **用户管理** | CRUD、角色分配、密码重置、回收站  |
| **角色管理** | CRUD、菜单权限分配、批量操作      |
| **部门管理** | 树形结构、数据权限隔离            |
| **日志管理** | 登录日志、操作日志查询            |

## 📖 详细文档

- [前端文档](./frontend/README.md)
- [后端文档](./backend/README.md)

## 📄 License

MIT License
