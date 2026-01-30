"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: storage.py
@DateTime: 2026/01/16 08:43:23
@Docs: 导入导出存储
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import uuid6

from app.import_export.config import get_exports_dir, get_imports_dir


@dataclass(frozen=True, slots=True)
class ImportPaths:
    """导入文件路径集合。

    Attributes:
        root (Path): 导入根目录。
        original (Path): 原始上传文件路径。
        meta (Path): 元数据 JSON 文件路径。
        parsed_parquet: 解析后的 Parquet 文件路径。
        errors_json (Path): 错误信息 JSON 文件路径。
        valid_parquet (Path): 验证后的有效数据 Parquet 文件路径。
    """

    root: Path
    original: Path
    meta: Path
    parsed_parquet: Path
    errors_json: Path
    valid_parquet: Path


def new_import_id() -> UUID:
    """生成新的导入 ID。

    Returns:
        UUID: UUIDv7 格式的导入 ID。
    """
    return uuid6.uuid7()


def ensure_dirs() -> None:
    """确保导入和导出目录存在。

    创建导入和导出目录（如果不存在）。
    """
    get_imports_dir().mkdir(parents=True, exist_ok=True)
    get_exports_dir().mkdir(parents=True, exist_ok=True)


def get_import_paths(import_id: UUID) -> ImportPaths:
    """获取导入文件路径集合。

    Args:
        import_id (UUID): 导入 ID。

    Returns:
        ImportPaths: 导入文件路径集合。
    """
    root = get_imports_dir() / str(import_id)
    return ImportPaths(
        root=root,
        original=root / "original",
        meta=root / "meta.json",
        parsed_parquet=root / "parsed.parquet",
        errors_json=root / "errors.json",
        valid_parquet=root / "valid.parquet",
    )


def write_meta(paths: ImportPaths, meta: dict[str, Any]) -> None:
    """写入导入元数据。

    Args:
        paths (ImportPaths): 导入文件路径集合。
        meta (dict[str, Any]): 元数据字典。
    """
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(paths: ImportPaths) -> dict[str, Any]:
    """读取导入元数据。

    Args:
        paths (ImportPaths): 导入文件路径集合。

    Returns:
        dict[str, Any]: 元数据字典。
    """
    return json.loads(paths.meta.read_text(encoding="utf-8"))


def sha256_file(file_path: Path) -> str:
    """计算文件的 SHA256 哈希值。

    Args:
        file_path (Path): 文件路径。

    Returns:
        str: SHA256 哈希值的十六进制字符串。
    """
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_unlink(path: Path) -> None:
    """安全删除文件。

    Args:
        path (Path): 文件路径。如果文件不存在或删除失败，则静默忽略。
    """
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def safe_rmtree(path: Path) -> None:
    """安全删除目录树。

    Args:
        path (Path): 目录路径。如果目录不存在或删除失败，则静默忽略。
    """
    try:
        if not path.exists():
            return
        for p in sorted(path.rglob("*"), reverse=True):
            if p.is_file():
                safe_unlink(p)
            else:
                try:
                    p.rmdir()
                except Exception:
                    pass
        try:
            path.rmdir()
        except Exception:
            pass
    except Exception:
        pass


def delete_export_file(path: str) -> None:
    """删除导出文件。

    Args:
        path (str): 导出文件路径。
    """
    safe_unlink(Path(path))


def create_export_path(filename: str) -> Path:
    """创建导出文件路径。

    Args:
        filename (str): 文件名。

    Returns:
        Path: 导出文件路径。文件名中的路径分隔符会被替换为下划线。
    """
    ensure_dirs()
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return get_exports_dir() / safe_name


def stat_size(path: Path) -> int:
    """获取文件大小。

    Args:
        path (Path): 文件路径。

    Returns:
        int: 文件大小（字节），如果文件不存在或获取失败则返回 0。
    """
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def now_ts() -> int:
    """获取当前时间戳。

    Returns:
        int: 当前 Unix 时间戳（秒）。
    """
    return int(time.time())


def cleanup_expired_imports(*, ttl_hours: int) -> int:
    """清理过期导入临时目录。

    Args:
        ttl_hours (int): 过期时间（小时）。

    Returns:
        int: 清理的目录数量。
    """
    imports_dir = get_imports_dir()
    if not imports_dir.exists():
        return 0
    cutoff = now_ts() - int(ttl_hours) * 3600
    cleaned = 0
    for item in imports_dir.iterdir():
        if not item.is_dir():
            continue
        meta_path = item / "meta.json"
        created_at = 0
        try:
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                created_at = int(meta.get("created_at") or 0)
        except Exception:
            created_at = 0
        try:
            if created_at and created_at >= cutoff:
                continue
            safe_rmtree(item)
            cleaned += 1
        except Exception:
            continue
    return cleaned
