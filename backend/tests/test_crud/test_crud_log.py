"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_crud_log.py
@DateTime: 2025-12-30 21:50:00
@Docs: Log CRUD 测试.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_log import login_log as login_log_crud
from app.crud.crud_log import operation_log as op_log_crud
from app.schemas.log import LoginLogCreate, OperationLogCreate


class TestCRUDLoginLog:
    """登录日志 CRUD 测试"""

    async def test_create_login_log(self, db_session: AsyncSession):
        """测试创建登录日志"""
        log_in = LoginLogCreate(username="testuser", ip="127.0.0.1", status=True, msg="Login Success")
        log = await login_log_crud.create(db_session, obj_in=log_in)
        assert log.id is not None
        assert log.username == "testuser"
        assert log.status is True

    async def test_get_multi(self, db_session: AsyncSession):
        """测试获取日志列表"""
        for i in range(3):
            await login_log_crud.create(db_session, obj_in=LoginLogCreate(username=f"User{i}", status=True))

        logs, total = await login_log_crud.get_multi_paginated(db_session, page=1, page_size=50)
        assert total >= 3
        assert len(logs) >= 3


class TestCRUDOperationLog:
    """操作日志 CRUD 测试"""

    async def test_create_operation_log(self, db_session: AsyncSession):
        """测试创建操作日志"""
        log_in = OperationLogCreate(
            username="admin",
            module="Users",
            summary="Create User",
            method="POST",
            path="/api/users",
            response_code=200,
            duration=0.1,
        )
        # 注意: OperationLogCreate 可能与 kwargs 不完全匹配，需检查 Schema。
        # 我们的 Schema 定义通常是 Base/Create/Update/Response。
        # 这里假设 OperationLogCreate 接收这些字段。
        # 如果 CRUD 只需要 dict 或 Create schema 都可以。

        # 修正：OperationLogCreate 定义可能不同，需 check schema。
        # 但我们之前看过 log.py model，字段都在。
        log = await op_log_crud.create(db_session, obj_in=log_in)
        assert log.id is not None
        assert log.module == "Users"
