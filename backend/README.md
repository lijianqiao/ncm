# NCM 后端

基于 **FastAPI + SQLAlchemy 2.0 (Async) + Celery** 构建的网络配置管理后端。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async) |
| 网络 | Scrapli (Async), Nornir, pysnmp, TextFSM |
| 任务 | Celery + Redis, Celery Beat |
| 存储 | PostgreSQL, Redis |
| 日志 | Structlog (JSON) |

## 支持设备

| 厂商 | 平台标识 |
|------|----------|
| Cisco | `cisco_iosxe`, `cisco_nxos`, `cisco_iosxr` |
| Huawei | `huawei_vrp` |
| H3C | `hp_comware` |
| Arista | `arista_eos` |
| Juniper | `juniper_junos` |

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境
cp .env.example .env

# 3. 数据库迁移
uv run alembic upgrade head

# 4. 初始化数据
uv run initial_data.py --init

# 5. 启动服务
uv run start.py           # API 服务
uv run start_worker.py    # Celery Worker
```

API 文档: http://127.0.0.1:8000/docs

## 关键配置

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ncm

# Redis
REDIS_URL=redis://localhost:6379/0

# 异步 SSH
ASYNC_SSH_TIMEOUT=60
ASYNC_SSH_SEMAPHORE=100
```

## 目录结构

```
app/
├── api/v1/endpoints/    # REST API
├── network/             # Scrapli/Nornir 封装
├── celery/tasks/        # 异步任务 (备份/发现/部署)
├── services/            # 业务逻辑
└── models/              # SQLAlchemy 模型
```

## License

MIT License
