"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_log_service.py
@DateTime: 2025-12-30 21:55:00
@Docs: Log Service 业务逻辑测试.
"""

# Mock
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_log import login_log as login_log_crud
from app.crud.crud_log import operation_log as op_log_crud
from app.services.log_service import LogService


@pytest.fixture
def log_service(db_session: AsyncSession):
    return LogService(db_session, login_log_crud, op_log_crud)


class TestLogServiceLogin:
    async def test_create_login_log(self, log_service: LogService):
        # Mock Request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = "Mozilla/5.0"

        log = await log_service.create_login_log(
            username="service_user", request=mock_request, status=True, msg="Service Test"
        )

        assert log.username == "service_user"
        assert log.ip == "192.168.1.1"
        assert log.msg == "Service Test"


class TestLogServiceQuery:
    async def test_get_login_logs_paginated(self, log_service: LogService):
        # Create some logs first via service
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent"

        for i in range(5):
            await log_service.create_login_log(username=f"U{i}", request=mock_request)

        logs, total = await log_service.get_login_logs_paginated(page=1, page_size=2)
        assert len(logs) == 2
        assert total >= 5
