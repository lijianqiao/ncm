# NCM 网络配置管理系统 (后端)

基于 FastAPI + SQLAlchemy 2.0 (Async) 构建的高性能网络自动化与管理系统后端。

## ✨ 核心特性

### 🕸️ 网络自动化 (Network Automation)
*   **配置备份**: 支持多品牌设备（Cisco, Huawei, H3C 等）的配置自动备份与版本对比。
*   **资产发现**: 基于 SNMP/SSH 的资产发现与 CMDB 自动对账。
*   **异步任务**: 基于 Celery 的大规模并行配置采集、下发与巡检。
*   **命令审计**: 记录所有网络配置变更操作，支持差异对比（Diff）。
*   **拓扑发现**: 自动采集 LLDP 邻居关系，构建网络物理拓扑。

### 🛡️ 基础架构 (Infrastructure)
*   **RBAC 权限**: 细粒度控制用户对设备、菜单及操作码的访问。
*   **审计日志**: 全量记录 API 调用与背景操作详情。
*   **安全防护**: JWT 双令牌轮换、CSRF 防护、HttpOnly Cookie。
*   **异步链路**: 全链路采用 `async/await`，适配高并发网络探测。

## 🚀 快速开始

### 1. 环境准备
```bash
uv venv --python 3.13
uv sync
```

### 2. 初始化环境
```bash
cp .env.example .env
# 配置 SQLALCHEMY_DATABASE_URI, REDIS_URL, CELERY_BROKER_URL 等
```

### 3. 数据库与数据
```bash
# 生成并应用迁移
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
uv run initial_data.py --init  # 初始账号: admin/123123
```

### 4. 启动服务
```bash
# 启动 API 服务
uv run start.py

# 启动 Celery Worker (处理网络采集任务)
uv run start_worker.py
```

## 📂 目录结构 (简)
*   `app/api/v1/endpoints/`: 业务接口（含备份、资产、巡检等）。
*   `app/celery/tasks/`: 网络自动化后台任务逻辑。
*   `app/services/`: 业务 Service 层（原子化编排）。
*   `app/network/`: 网络驱动与协议封装（Netmiko/Scrapli等集成）。

