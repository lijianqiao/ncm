"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log_service.py
@DateTime: 2025-12-30 12:25:00
@Docs: 日志服务业务逻辑 (Logging Service Logic).
"""

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from user_agents import parse

from app.core.decorator import transactional
from app.crud.crud_log import CRUDLoginLog, CRUDOperationLog
from app.models.log import LoginLog, OperationLog
from app.schemas.log import LoginLogCreate


class LogService:
    """
    日志服务类。
    """

    def __init__(self, db: AsyncSession, login_log_crud: CRUDLoginLog, operation_log_crud: CRUDOperationLog):
        self.db = db
        self.login_log_crud = login_log_crud
        self.operation_log_crud = operation_log_crud

    async def get_login_logs(self, skip: int = 0, limit: int = 100) -> list[LoginLog]:
        """
        获取登录日志列表。
        """
        return await self.login_log_crud.get_multi(self.db, skip=skip, limit=limit)

    async def get_login_logs_paginated(
        self, page: int = 1, page_size: int = 20, *, keyword: str | None = None
    ) -> tuple[list[LoginLog], int]:
        """
        获取分页登录日志列表。
        """
        return await self.login_log_crud.get_multi_paginated(self.db, page=page, page_size=page_size, keyword=keyword)

    async def get_operation_logs(self, skip: int = 0, limit: int = 100) -> list[OperationLog]:
        """
        获取操作日志列表。
        """
        return await self.operation_log_crud.get_multi(self.db, skip=skip, limit=limit)

    async def get_operation_logs_paginated(
        self, page: int = 1, page_size: int = 20, *, keyword: str | None = None
    ) -> tuple[list[OperationLog], int]:
        """
        获取分页操作日志列表。
        """
        return await self.operation_log_crud.get_multi_paginated(
            self.db, page=page, page_size=page_size, keyword=keyword
        )

    @transactional()
    async def create_login_log(
        self,
        *,
        user_id: uuid.UUID | str | None = None,
        username: str | None = None,
        request: Request,
        status: bool = True,
        msg: str = "Login Success",
    ) -> LoginLog:
        """
        创建登录日志。
        """
        ip = request.client.host if request.client else None
        ua_string = request.headers.get("user-agent", "")
        user_agent = parse(ua_string)

        # 将 user_id 转为 UUID 对象 (如果非空)
        final_user_id: uuid.UUID | None = None
        if user_id:
            if isinstance(user_id, str):
                try:
                    final_user_id = uuid.UUID(user_id)
                except ValueError:
                    final_user_id = None
            else:
                final_user_id = user_id

        log_in = LoginLogCreate(
            user_id=final_user_id,
            username=username,
            ip=ip,
            user_agent=str(user_agent),
            browser=f"{user_agent.browser.family} {user_agent.browser.version_string}",
            os=f"{user_agent.os.family} {user_agent.os.version_string}",
            device=user_agent.device.family,
            status=status,
            msg=msg,
        )

        return await self.login_log_crud.create(self.db, obj_in=log_in)
