"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: config.py
@DateTime: 2026/01/16 08:45:23
@Docs: 导入导出配置
"""

import tempfile
from pathlib import Path

from app.core.config import settings


def get_import_export_tmp_dir() -> Path:
    configured = str(settings.IMPORT_EXPORT_TMP_DIR or "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "ncm"


def get_imports_dir() -> Path:
    return get_import_export_tmp_dir() / "imports"


def get_exports_dir() -> Path:
    return get_import_export_tmp_dir() / "exports"
