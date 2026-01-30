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
    """获取导入导出临时目录路径。

    Returns:
        Path: 临时目录路径。如果配置了 IMPORT_EXPORT_TMP_DIR 则使用配置值，否则使用系统临时目录下的 ncm 子目录。
    """
    configured = str(settings.IMPORT_EXPORT_TMP_DIR or "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "ncm"


def get_imports_dir() -> Path:
    """获取导入文件存储目录路径。

    Returns:
        Path: 导入文件存储目录路径。
    """
    return get_import_export_tmp_dir() / "imports"


def get_exports_dir() -> Path:
    """获取导出文件存储目录路径。

    Returns:
        Path: 导出文件存储目录路径。
    """
    return get_import_export_tmp_dir() / "exports"
