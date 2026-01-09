"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: diff_service.py
@DateTime: 2026-01-10 03:40:00
@Docs: 配置差异服务 (Diff Service).

基于备份内容生成 unified diff，用于配置变更告警与差异查看。
"""

import difflib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BackupStatus
from app.crud.crud_backup import CRUDBackup
from app.models.backup import Backup


class DiffService:
    """配置差异服务。"""

    def __init__(self, db: AsyncSession, backup_crud: CRUDBackup):
        self.db = db
        self.backup_crud = backup_crud

    async def get_latest_pair(self, device_id: UUID) -> tuple[Backup | None, Backup | None]:
        """
        获取用于对比的两份备份（最新与上一份成功备份）。

        Returns:
            (new_backup, old_backup)
        """
        query = (
            select(Backup)
            .where(Backup.device_id == device_id)
            .where(Backup.is_deleted.is_(False))
            .where(Backup.status == BackupStatus.SUCCESS.value)
            .order_by(Backup.created_at.desc())
            .limit(2)
        )
        result = await self.db.execute(query)
        backups = list(result.scalars().all())
        if not backups:
            return None, None
        if len(backups) == 1:
            return backups[0], None
        return backups[0], backups[1]

    @staticmethod
    def _normalize_lines(text: str) -> list[str]:
        """
        预处理文本行：
        - 去除行尾空白
        - 去除空行（避免无意义变更）
        """
        lines = []
        for line in text.splitlines():
            s = line.rstrip()
            if not s:
                continue
            lines.append(s)
        return lines

    def compute_unified_diff(self, old_text: str, new_text: str, *, context_lines: int = 3) -> str:
        """
        计算 unified diff。
        """
        old_lines = self._normalize_lines(old_text)
        new_lines = self._normalize_lines(new_text)

        diff_iter = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            lineterm="",
            n=context_lines,
        )
        return "\n".join(diff_iter)

    @staticmethod
    def should_alert(diff_text: str) -> bool:
        """diff 不为空则认为需要告警。"""
        return bool(diff_text.strip())

