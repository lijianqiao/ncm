"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: session_service.py
@DateTime: 2026-01-07 00:00:00
@Docs: 在线会话管理服务（在线列表/强制下线）。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.session_store import list_online_sessions, remove_online_session, remove_online_sessions
from app.core.token_store import (
    revoke_user_access_now,
    revoke_user_refresh,
    revoke_users_access_now,
    revoke_users_refresh,
)
from app.crud.crud_user import CRUDUser
from app.schemas.common import BatchOperationResult
from app.schemas.session import OnlineSessionResponse
from app.services.base import BaseService


class SessionService(BaseService):
    """
    在线会话管理服务类。

    提供在线会话列表查询和强制下线功能。
    """

    def __init__(self, db: AsyncSession, user_crud: CRUDUser):
        """
        初始化会话服务。

        Args:
            db: 异步数据库会话
            user_crud: 用户 CRUD 实例
        """
        super().__init__(db)
        self.user_crud = user_crud

    async def list_online(
        self, *, page: int = 1, page_size: int = 20, keyword: str | None = None
    ) -> tuple[list[OnlineSessionResponse], int]:
        """
        获取在线会话列表（分页）。

        Args:
            page: 页码（从 1 开始）
            page_size: 每页记录数
            keyword: 搜索关键字（可选）

        Returns:
            tuple[list[OnlineSessionResponse], int]: (在线会话列表, 总数)
        """
        sessions, total = await list_online_sessions(page=page, page_size=page_size, keyword=keyword)

        items: list[OnlineSessionResponse] = []
        for s in sessions:
            try:
                uid = UUID(str(s.user_id))
            except Exception:
                continue

            items.append(
                OnlineSessionResponse(
                    user_id=uid,
                    username=s.username,
                    ip=s.ip,
                    user_agent=s.user_agent,
                    login_at=datetime.fromtimestamp(float(s.login_at), tz=UTC),
                    last_seen_at=datetime.fromtimestamp(float(s.last_seen_at), tz=UTC),
                )
            )

        return items, total

    async def kick_user(self, *, user_id: UUID) -> None:
        """
        强制下线单个用户。

        Args:
            user_id: 用户 ID

        Raises:
            NotFoundException: 用户不存在
        """
        user = await self.user_crud.get(self.db, id=user_id)
        if not user:
            raise NotFoundException(message="用户不存在")

        await revoke_user_refresh(user_id=str(user_id))
        await revoke_user_access_now(user_id=str(user_id))
        await remove_online_session(user_id=str(user_id))

    async def kick_users(self, *, user_ids: list[UUID]) -> BatchOperationResult:
        """
        批量强制下线用户。

        Args:
            user_ids: 用户 ID 列表

        Returns:
            BatchOperationResult: 批量操作结果
        """
        unique_ids = list(dict.fromkeys(user_ids))
        if not unique_ids:
            return self._build_batch_result(0, [], message="无用户需要下线")

        # 仅踢存在的用户（避免把错误 ID 当成功）
        success: list[UUID] = []
        failed: list[UUID] = []

        for uid in unique_ids:
            user = await self.user_crud.get(self.db, id=uid)
            if not user:
                failed.append(uid)
            else:
                success.append(uid)

        if success:
            str_ids = [str(x) for x in success]
            await revoke_users_refresh(user_ids=str_ids)
            await revoke_users_access_now(user_ids=str_ids)
            await remove_online_sessions(user_ids=str_ids)

        return self._build_batch_result(len(success), failed, message="强制下线完成")
