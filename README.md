# Admin RBAC 后台管理系统

基于 **Vue 3 + FastAPI** 的现代化后台管理系统，提供完整的 RBAC 权限控制、用户管理、审计日志等核心功能。

## ✨ 核心特性

- **RBAC 权限控制**：用户 - 角色 - 菜单/权限 三级权限模型
- **动态路由**：根据用户权限动态生成前端路由和菜单
- **软删除与回收站**：支持数据软删除及恢复
- **审计日志**：自动记录登录日志和操作日志
- **会话管理**：在线用户列表、强制下线
- **部门管理**：树形结构展示、层级管理、回收站功能
- **安全防护**：JWT 认证 + CSRF 防护 + 密码复杂度验证

## 🛠️ 技术栈

| 层级     | 技术                                                     |
| -------- | -------------------------------------------------------- |
| **前端** | Vue 3, TypeScript, Pinia, Vue Router, Naive UI, Vite     |
| **后端** | FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, PostgreSQL |
| **缓存** | Redis                                                    |
| **日志** | Structlog (JSON 格式)                                    |

## 📂 项目结构

```
admin-rbac/
├── frontend/          # 前端项目 (Vue 3)
│   ├── src/
│   │   ├── api/       # API 接口定义
│   │   ├── components/# 公共组件
│   │   ├── layouts/   # 布局组件
│   │   ├── router/    # 路由配置
│   │   ├── stores/    # Pinia 状态管理
│   │   ├── views/     # 页面视图
│   │   └── utils/     # 工具函数
│   └── README.md
│
├── backend/           # 后端项目 (FastAPI)
│   ├── app/
│   │   ├── api/       # API 接口层
│   │   ├── core/      # 核心配置 (安全、日志、中间件)
│   │   ├── crud/      # 数据访问层
│   │   ├── models/    # SQLAlchemy 模型
│   │   ├── schemas/   # Pydantic 校验模型
│   │   ├── utils/     # 工具类
│   │   └── services/  # 业务逻辑层
│   ├── tests/         # 测试套件
│   └── README.md
│
└── README.md          # 本文件
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

# 创建虚拟环境
uv venv --python 3.13
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置数据库连接等

# 数据库迁移
uv run alembic upgrade head

# 初始化管理员账号
uv run initial_data.py --init

# 启动服务
uv run start.py
```

后端 API 文档：http://127.0.0.1:8000/docs

### 2. 前端启动

```bash
cd frontend

# 安装依赖
pnpm install

# 配置环境变量
cp .env.example .env.development
# 编辑 .env.development 设置 API 地址等

# 启动开发服务
pnpm dev
```

前端访问地址：http://127.0.0.1:5173

### 3. 默认账号

| 用户名 | 密码     | 角色       |
| ------ | -------- | ---------- |
| admin  | password | 超级管理员 |

> ⚠️ 生产环境请务必修改默认密码！

## 📋 功能模块

| 模块         | 功能                                       |
| ------------ | ------------------------------------------ |
| **仪表盘**   | 系统统计、最近登录日志                     |
| **用户管理** | CRUD、角色分配、密码重置、批量操作、回收站 |
| **角色管理** | CRUD、菜单权限分配、批量操作、回收站       |
| **菜单管理** | 目录/菜单/权限点配置、树形结构管理         |
| **部门管理** | 树形结构展示、层级管理、回收站功能         |
| **日志管理** | 登录日志、操作日志查询                     |
| **会话管理** | 在线用户列表、强制下线                     |

## 🔒 安全特性

- **JWT 双 Token**：Access Token (短期) + Refresh Token (HttpOnly Cookie)
- **CSRF 防护**：双提交 Cookie 模式
- **密码安全**：Argon2/Bcrypt 加密，可配置复杂度要求
- **限流保护**：登录接口限流 (5次/分钟)
- **环境检查**：生产环境阻止弱密码和不安全配置

## 📖 详细文档

- [前端文档](https://github.com/lijianqiao/frontend/blob/main/README.md)
- [后端文档](https://github.com/lijianqiao/backend/blob/master/README.md)
- [API 文档](https://github.com/lijianqiao/frontend/blob/main/api.md)

## 📄 License

MIT License
