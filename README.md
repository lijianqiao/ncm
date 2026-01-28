# NCM 网络配置管理系统

基于 **Vue 3 + FastAPI** 构建的企业级网络配置管理平台，专注于网络自动化与配置生命周期管理。

## 核心功能

| 功能 | 说明 |
|------|------|
| **配置备份** | 多厂商设备配置自动采集、版本管理、差异对比 |
| **批量下发** | Jinja2 模板变量、OTP 动态密码、断点续传 |
| **资产发现** | SNMP/SSH 网段扫描、设备指纹识别、CMDB 对账 |
| **拓扑发现** | LLDP 邻居采集、物理拓扑可视化（vis-network） |
| **告警管理** | 配置变更告警、设备离线检测 |

## 技术架构

```
前端: Vue 3 + TypeScript + Naive UI + Pinia
后端: FastAPI + SQLAlchemy 2.0 (Async) + Celery
网络: Scrapli (Async) + Nornir + SNMP
存储: PostgreSQL + Redis
```

**支持设备**：H3C Comware、Huawei VRP、Cisco IOS

## 快速开始

### 环境要求

- Node.js >= 20, Python >= 3.13
- PostgreSQL >= 16, Redis >= 6

### 后端

```bash
cd backend
uv sync                                    # 安装依赖
cp .env.example .env                       # 配置环境变量
uv run alembic upgrade head                # 数据库迁移
uv run initial_data.py --init              # 初始化管理员
uv run start.py                            # 启动 API
uv run start_worker.py                     # 启动 Celery Worker
```

### 前端

```bash
cd frontend
pnpm install                               # 安装依赖
cp .env.example .env.development           # 配置环境变量
pnpm dev                                   # 启动开发服务
```

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | 123123 | 超级管理员 |

> 生产环境请务必修改默认密码

## 访问地址

- 前端: <http://127.0.0.1:5173>
- API 文档: <http://127.0.0.1:8000/docs>

## 文档

- [后端文档](./backend/README.md)
- [前端文档](./frontend/README.md)

## License

MIT License
