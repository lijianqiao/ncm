# fastapi_import_export

一个可复用的 FastAPI 导入导出基础库（上传→解析→校验→预览→提交、导出 CSV/Excel、模板生成、临时文件清理）。

本库只提供通用基础设施：具体业务字段规则（例如“设备导入导出”）通过注入 handler（validate/persist/export/template）实现。

## 依赖

- fastapi
- pydantic
- polars
- openpyxl
- uuid6
- 可选：redis（或兼容客户端，用于导入提交锁）

## 快速开始

```python
from fastapi_import_export import ImportExportService

svc = ImportExportService(
    db=db,                       # 任意对象，原样传递给你的 handler
    redis_client=redis_client,   # 可选
    base_dir=None,               # 可选；默认从环境变量或系统临时目录推导
    max_upload_mb=20,
    lock_ttl_seconds=300,
)
```

环境变量（可选）：
- IMPORT_EXPORT_BASE_DIR / IMPORT_EXPORT_TMP_DIR：导入导出根目录
- IMPORT_EXPORT_IMPORTS_DIRNAME：imports 子目录名（默认 imports）
- IMPORT_EXPORT_EXPORTS_DIRNAME：exports 子目录名（默认 exports）

更多端到端 FastAPI 接入示例、handler 签名、存储结构说明，请参考仓库内的适配说明或自行按需封装路由。

