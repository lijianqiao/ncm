# import_export 模块使用说明（可复用的 FastAPI 导入导出）

本目录提供一套“上传 → 解析 → 校验 → 预览 → 提交导入”以及“导出 CSV/Excel、下载模板”的通用能力，适合在 FastAPI 项目中复用。模块本身不包含任何业务字段规则；业务方通过注入函数（handler）实现具体领域逻辑（例如设备/用户/资产等）。

> 说明：为了发布到 PyPI，本仓库已将“通用导入导出基础设施”抽为独立包 `fastapi_import_export/`；`app/import_export/` 作为 NCM 项目的适配入口（便于项目内统一导入）。

---

## 目录结构

- `config.py`：导入导出临时目录配置（imports/exports 根目录）。
- `storage.py`：文件落盘、meta 管理、checksum、过期清理等。
- `parse.py`：解析 CSV/Excel 为 Polars DataFrame，并附加 `row_number` 行号。
- `schemas.py`：导入导出相关 Pydantic DTO。
- `service.py`：通用 `ImportExportService`（面向 FastAPI 的业务编排，依赖注入各种 handler）。
- `__init__.py`：包入口，聚合导出常用类型与函数（建议其他模块优先从这里导入）。

---

## 依赖（建议 PyPI requirements）

必需依赖（核心能力）：

- `fastapi`：`UploadFile` 类型与 Web 接入。
- `pydantic`：请求/响应模型（schemas）。
- `sqlalchemy`（async）：示例中使用 `AsyncSession`，用于把 `db session` 透传给 handler。
- `polars`：统一的表格数据结构（校验/预览/落库入口）。
- `openpyxl`：Excel 解析与模板/导出写入（避免 pandas→polars 需要 pyarrow 的问题）。
- `uuid6`：生成 UUIDv7 风格的导入任务 ID。

可选依赖：

- `redis`（或兼容客户端）：用于提交导入时的分布式锁（防止同一 import_id 重复 commit）。不提供也能运行（退化为无锁）。

说明：

- `parse.py` 会优先尝试 `polars.read_excel`；不可用时使用 `openpyxl` 读取，保证不依赖 `pyarrow`。

---

## 核心概念

### 1) Import ID 与文件落盘

一次导入会生成一个 `import_id`，并在 imports 目录下创建文件夹：

- `original.*`：原始上传文件（csv/xlsx）
- `meta.json`：导入元信息（checksum、大小、状态等）
- `parsed.parquet`：解析并列名归一后的完整数据（含 `row_number`）
- `valid.parquet`：通过业务校验的有效行（含 `row_number`）
- `errors.json`：校验错误明细（业务方定义结构，默认 list[dict]）

这些文件由 `storage.py` 管理。

### 2) 业务注入点（handler）

通用服务不懂“哪些字段必须有”、“怎么查重”、“怎么写库”。业务方需要提供：

- `column_aliases`：列名映射表（例如把“IP地址”映射到 `ip_address`）
- `validate_fn(db, df, allow_overwrite=...) -> (valid_df, errors)`：校验并返回有效行与错误列表
- `persist_fn(db, valid_df, allow_overwrite=...) -> imported_rows`：把有效行写入数据库，返回导入行数
- `df_fn(db) -> DataFrame`：导出时生成数据表
- `builder(path)`：生成模板文件（xlsx）

---

## API 速查（service.py）

通用服务：`app.import_export.service.ImportExportService`

### 初始化

```python
from app.import_export import ImportExportService

svc = ImportExportService(
    db=db_session,
    redis_client=redis_client,     # 可选
    max_upload_mb=20,              # 可配置
    lock_ttl_seconds=300,          # 可配置
)
```

### 导出

```python
result = await svc.export_table(
    fmt="csv",                     # "csv" | "xlsx"
    filename_prefix="devices",
    df_fn=export_df_handler,
)
```

返回 `ExportResult(path, filename, media_type)`，FastAPI 里通常用 `FileResponse` 返回并在后台删除临时文件。

### 下载模板

```python
result = await svc.build_template(
    filename_prefix="device_import_template",
    builder=template_builder,
)
```

### 上传 + 解析 + 校验

```python
resp = await svc.upload_parse_validate(
    file=file,                     # fastapi.UploadFile
    column_aliases=COLUMN_ALIASES,  # dict[str, str]
    validate_fn=validate_handler,   # 业务校验
    allow_overwrite=False,          # 可选：覆盖策略透传给校验器
)
```

返回 `ImportValidateResponse`（包含 `import_id/checksum/total_rows/valid_rows/error_rows/errors`）。

### 预览

```python
resp = await svc.preview(
    import_id=import_id,
    checksum=checksum,
    page=1,
    page_size=20,
    kind="all",                    # "all" | "valid"
)
```

### 提交导入（单事务 + 可选分布式锁）

```python
resp = await svc.commit(
    body=ImportCommitRequest(import_id=..., checksum=..., allow_overwrite=True),
    persist_fn=persist_handler,
    lock_namespace="import",       # 可配置命名空间，避免冲突
)
```

---

## FastAPI 端到端接入示例（通用写法）

下面示例展示一种“完全通用”的路由形态；业务差异全部由 handler 注入解决。

```python
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession

from app.import_export import (
    ImportExportService,
    ImportCommitRequest,
    delete_export_file,
)

router = APIRouter(prefix="/import-export", tags=["import-export"])

def get_db() -> AsyncSession:
    ...

def get_svc(db: AsyncSession = Depends(get_db)) -> ImportExportService:
    return ImportExportService(db=db)  # redis_client 可按需注入

@router.get("/export")
async def export_any(
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
    svc: ImportExportService = Depends(get_svc),
):
    result = await svc.export_table(fmt=fmt, filename_prefix="items", df_fn=export_df_handler)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )

@router.get("/template")
async def template_any(svc: ImportExportService = Depends(get_svc)):
    result = await svc.build_template(filename_prefix="items_template", builder=template_builder)
    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(delete_export_file, str(result.path)),
    )

@router.post("/upload-validate")
async def upload_validate_any(
    file: UploadFile = File(...),
    allow_overwrite: bool = Form(False),
    svc: ImportExportService = Depends(get_svc),
):
    return await svc.upload_parse_validate(
        file=file,
        column_aliases=COLUMN_ALIASES,
        validate_fn=validate_handler,
        allow_overwrite=allow_overwrite,
    )

@router.get("/preview")
async def preview_any(
    import_id: str = Query(...),
    checksum: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    kind: str = Query("all", pattern="^(all|valid)$"),
    svc: ImportExportService = Depends(get_svc),
):
    return await svc.preview(
        import_id=UUID(import_id),
        checksum=checksum,
        page=page,
        page_size=page_size,
        kind=kind,
    )

@router.post("/commit")
async def commit_any(body: ImportCommitRequest, svc: ImportExportService = Depends(get_svc)):
    return await svc.commit(body=body, persist_fn=persist_handler, lock_namespace="import")
```

---

## 业务 handler 参考（关键签名）

### 校验函数 validate_fn

要求：

- 输入 df 一定含 `row_number`（从 1 开始，便于错误定位）
- 返回 `valid_df`（只保留可导入行，且建议仍保留 `row_number`）与 `errors`

```python
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

async def validate_handler(
    db: AsyncSession,
    df: pl.DataFrame,
    *,
    allow_overwrite: bool = False,
) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    # 1) 检查必需列
    # 2) 检查格式/枚举/引用完整性
    # 3) 查库去重（如果 allow_overwrite=True，可跳过“已存在”错误）
    # 4) 生成 valid_df
    return valid_df, errors
```

### 落库函数 persist_fn

```python
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

async def persist_handler(
    db: AsyncSession,
    valid_df: pl.DataFrame,
    *,
    allow_overwrite: bool = False,
) -> int:
    # 在单事务中写入；allow_overwrite=True 时按业务规则更新
    return imported_rows
```

---

## 存储目录与可配置项

当前实现通过 `config.py` 决定 imports/exports 根目录：

- 优先使用配置项 `IMPORT_EXPORT_TMP_DIR`
- 否则使用系统临时目录下的 `ncm/`

> 计划发布到 PyPI 时，建议把这一层改为更通用的参数来源（例如环境变量、函数参数、或可注入的路径 provider），避免依赖项目内的 `settings`。

过期清理：

- `cleanup_expired_imports(ttl_hours=...)` 会遍历 imports 目录，根据 `meta.json.created_at` 清理过期导入目录。

---

## 发布到 PyPI 的建议（通用化清单）

要做到“拿到任何 FastAPI 项目都能用”，建议在发布前完成：

- 去耦 `config.py` 对项目 `settings` 的依赖：改为 env/参数/注入式配置。
- 去耦模块路径 `app.import_export.*`：将包顶层命名为独立包（例如 `fastapi_import_export`），并调整 import 路径。
- 将 `storage` 的 base_dir 从全局函数改为 `ImportExportService` 初始化参数（更适合多应用/多租户）。
- 可选：把 `AsyncSession` 也泛化为 Protocol（允许任何 db client），当前版本偏向 SQLAlchemy。

---

## 安全与实践建议

- 不要在 `errors.json` / 响应中返回敏感字段（例如密码明文）。
- 对上传文件大小做限制（已支持 `max_upload_mb`）。
- 提交导入建议启用 Redis 锁，避免同一导入被并发提交导致重复写入。
