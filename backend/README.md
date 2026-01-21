# NCM 网络配置管理系统（后端）

基于 **FastAPI + SQLAlchemy 2.0 (Async)** 构建的网络配置管理系统后端，专注于网络自动化与配置生命周期管理。

## 🌟 网络自动化核心

### 异步网络任务架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  FastAPI    │───▶│   Celery    │───▶│  Scrapli    │
│  REST API   │    │   Worker    │    │   Async     │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                   ┌──────┴──────┐
                   │   Nornir    │
                   │  Inventory  │
                   └─────────────┘
```

### 关键模块

| 模块           | 路径                             | 功能                                                             |
| -------------- | -------------------------------- | ---------------------------------------------------------------- |
| **平台配置**   | `app/network/platform_config.py` | 统一命令映射、Scrapli 参数、NTC 解析模板                         |
| **异步任务**   | `app/network/async_tasks.py`     | Scrapli Async 封装：`async_send_command`、`async_collect_config` |
| **异步执行器** | `app/network/async_runner.py`    | 并发控制、结果聚合、超时处理                                     |
| **备份任务**   | `app/celery/tasks/backup.py`     | 配置采集、MD5 去重、变更告警                                     |
| **发现任务**   | `app/celery/tasks/discovery.py`  | SNMP 扫描、LLDP 拓扑、CMDB 对账                                  |
| **部署任务**   | `app/celery/tasks/deploy.py`     | 批量下发、命令审计、回滚支持                                     |

### 支持的设备平台

| 厂商    | 平台标识        | Scrapli Driver         |
| ------- | --------------- | ---------------------- |
| Cisco   | `cisco_iosxe`   | `AsyncIOSXEDriver`     |
| Cisco   | `cisco_nxos`    | `AsyncNXOSDriver`      |
| Huawei  | `huawei_vrp`    | `AsyncHuaweiVRPDriver` |
| H3C     | `hp_comware`    | `AsyncHPComwareDriver` |
| Arista  | `arista_eos`    | `AsyncEOSDriver`       |
| Juniper | `juniper_junos` | `AsyncJunosDriver`     |

## ✨ 核心特性

### 🕸️ 网络自动化

- **配置备份**：多品牌设备配置自动备份、MD5 去重、版本差异对比
- **批量下发**：模板变量替换、OTP 动态密码、断点续传
- **资产发现**：SNMP/SSH 扫描、设备指纹识别、CMDB 自动对账
- **拓扑发现**：LLDP/CDP 邻居采集，构建物理拓扑
- **告警系统**：配置变更检测、Webhook 通知

### 🛡️ 基础架构

- **RBAC 权限**：细粒度控制用户对设备、菜单及操作码的访问
- **审计日志**：全量记录 API 调用与后台操作详情
- **安全防护**：JWT 双令牌轮换、CSRF 防护、HttpOnly Cookie
- **异步链路**：全链路 `async/await`，支持 100+ 设备并行采集

## 🚀 快速开始

### 1. 环境准备

- Python >= 3.13
- PostgreSQL >= 16
- Redis >= 6

```bash
uv venv --python 3.13
uv sync
```

### 2. 环境配置

```bash
cp .env.example .env
# 按需修改：数据库、Redis、SECRET_KEY、网络任务参数等
```

关键网络配置项：

```env
# 异步 SSH 配置
ASYNC_SSH_TIMEOUT=60
ASYNC_SSH_CONNECT_TIMEOUT=30
ASYNC_SSH_SEMAPHORE=100

# Scrapli 连接池配置
SCRAPLI_POOL_MAX_CONNECTIONS=100
SCRAPLI_POOL_MAX_IDLE_TIME=300
SCRAPLI_POOL_MAX_AGE=3600

# 定时扫描网段
SCAN_SCHEDULED_SUBNETS=192.168.1.0/24,10.0.0.0/24
```

### 3. 数据库初始化

```bash
# 生成数据库迁移文件
uv run alembic revision --autogenerate -m "Initial migration"

# 应用迁移
uv run alembic upgrade head

# 初始化管理员账号
uv run initial_data.py --init
```

### 4. 启动服务

```bash
# 启动 API 服务
uv run start.py

# 启动 Celery Worker（网络任务处理）
uv run start_worker.py
```

API 文档：http://127.0.0.1:8000/docs

## 🧩 模板库（表单化参数 V2）

### 相关接口

- `GET /api/v1/templates/param-types` 获取参数类型元数据
- `POST /api/v1/templates/extract-vars` 从模板内容提取变量
- `POST /api/v1/templates/v2` 创建模板（表单化参数）
- `PUT /api/v1/templates/v2/{template_id}` 更新模板（表单化参数）
- `GET /api/v1/templates/v2/{template_id}` 获取模板详情（含参数列表）
- `GET /api/v1/templates/examples` 获取示例模板列表（前端展示/初始化）

### 模板变量写法

- 推荐使用 **顶层变量**（便于 `extract-vars` 自动提取）
- 同时兼容 `params.xxx` 写法

示例：

```jinja
interface {{ interface_name }}
ip address {{ ip_address }} {{ netmask }}
```

## 📂 目录结构

```
app/
├── api/v1/endpoints/     # REST API 接口
│   ├── backups.py        # 配置备份
│   ├── devices.py        # 设备管理
│   ├── discovery.py      # 资产发现
│   ├── topology.py       # 拓扑发现
│   └── alerts.py         # 告警管理
│
├── network/              # 网络驱动层
│   ├── platform_config.py    # 平台配置中心
│   ├── async_tasks.py        # Scrapli 异步任务
│   ├── async_runner.py       # 并发执行器
│   └── nornir_config.py      # Nornir 初始化
│
├── celery/tasks/         # Celery 后台任务
│   ├── backup.py         # 配置备份任务
│   ├── discovery.py      # 网络发现任务
│   └── deploy.py         # 配置下发任务
│
├── services/             # 业务逻辑层
│   ├── backup_service.py
│   ├── device_service.py
│   └── alert_service.py
│
└── models/               # SQLAlchemy 模型
    ├── device.py
    ├── backup.py
    └── alert.py
```

## 🧩 常见问题

### 1) Scrapli 平台未找到

确保设备的 `platform` 字段使用正确的 Scrapli 平台标识（如 `hp_comware` 而非 `h3c`）。系统会自动转换常见厂商名。

### 2) SSH 连接超时

调整 `.env` 中的超时参数：

```env
ASYNC_SSH_TIMEOUT=120
ASYNC_SSH_CONNECT_TIMEOUT=60
```

### 3) Celery Worker 任务不执行

确保 Redis 服务正常，检查 Worker 日志：

```bash
uv run start_worker.py
```

## 📄 License

MIT License
