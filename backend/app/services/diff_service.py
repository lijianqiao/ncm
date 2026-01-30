"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: diff_service.py
@DateTime: 2026-01-10 03:40:00
@Docs: 配置差异服务 (Diff Service).

基于备份内容生成 unified diff，用于配置变更告警与差异查看。
"""

import asyncio
import difflib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import BackupStatus
from app.crud.crud_backup import CRUDBackup
from app.models.backup import Backup

# 大文本阈值：超过此大小使用线程池处理避免阻塞
LARGE_TEXT_THRESHOLD = 100 * 1024  # 100KB


class DiffService:
    """
    配置差异服务。

    基于备份内容生成 unified diff，用于配置变更告警与差异查看。
    """

    def __init__(self, db: AsyncSession, backup_crud: CRUDBackup):
        """
        初始化配置差异服务。

        Args:
            db: 异步数据库会话
            backup_crud: 备份 CRUD 实例
        """
        self.db = db
        self.backup_crud = backup_crud

    async def get_latest_pair(self, device_id: UUID) -> tuple[Backup | None, Backup | None]:
        """
        获取用于对比的两份备份（最新与上一份成功备份）。

        Args:
            device_id: 设备 ID

        Returns:
            tuple[Backup | None, Backup | None]: (最新备份, 上一份备份)，如果只有一份则返回 (backup, None)，如果没有则返回 (None, None)
        """
        query = (
            select(Backup)
            .options(selectinload(Backup.device))
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

        Args:
            text: 原始文本

        Returns:
            list[str]: 规范化后的行列表
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
        计算 unified diff（同步版本，适用于小文本）。

        Args:
            old_text: 旧文本内容
            new_text: 新文本内容
            context_lines: 上下文行数（默认 3）

        Returns:
            str: unified diff 字符串
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

    async def compute_unified_diff_async(self, old_text: str, new_text: str, *, context_lines: int = 3) -> str:
        """
        计算 unified diff（异步版本）。

        对于大文本（超过 100KB），使用线程池执行以避免阻塞事件循环。

        Args:
            old_text: 旧文本内容
            new_text: 新文本内容
            context_lines: 上下文行数（默认 3）

        Returns:
            str: unified diff 字符串
        """
        total_size = len(old_text) + len(new_text)
        if total_size > LARGE_TEXT_THRESHOLD:
            # 大文本使用线程池
            return await asyncio.to_thread(self.compute_unified_diff, old_text, new_text, context_lines=context_lines)
        # 小文本直接计算
        return self.compute_unified_diff(old_text, new_text, context_lines=context_lines)

    @staticmethod
    def should_alert(diff_text: str) -> bool:
        """
        判断 diff 是否需要告警。

        diff 不为空则认为需要告警。

        Args:
            diff_text: diff 文本内容

        Returns:
            bool: 是否需要告警
        """
        return bool(diff_text.strip())
