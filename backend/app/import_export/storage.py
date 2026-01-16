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
    root: Path
    original: Path
    meta: Path
    parsed_parquet: Path
    errors_json: Path
    valid_parquet: Path


def new_import_id() -> UUID:
    return uuid6.uuid7()


def ensure_dirs() -> None:
    get_imports_dir().mkdir(parents=True, exist_ok=True)
    get_exports_dir().mkdir(parents=True, exist_ok=True)


def get_import_paths(import_id: UUID) -> ImportPaths:
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
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(paths: ImportPaths) -> dict[str, Any]:
    return json.loads(paths.meta.read_text(encoding="utf-8"))


def sha256_file(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def safe_rmtree(path: Path) -> None:
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
    safe_unlink(Path(path))


def create_export_path(filename: str) -> Path:
    ensure_dirs()
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return get_exports_dir() / safe_name


def stat_size(path: Path) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def now_ts() -> int:
    return int(time.time())


def cleanup_expired_imports(*, ttl_hours: int) -> int:
    """清理过期导入临时目录，返回清理数量。"""
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
