"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_logs.py
@DateTime: 2025-12-30 22:00:00
@Docs: Log API 接口测试.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.crud_log import login_log, operation_log
from app.schemas.log import LoginLogCreate, OperationLogCreate


class TestLogsRead:
    async def test_read_login_logs(self, client: AsyncClient, auth_headers: dict):
        """测试获取登录日志"""
        response = await client.get(f"{settings.API_V1_STR}/logs/login", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    async def test_read_login_logs_keyword_mapping_status(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试登录日志 keyword 对状态的映射过滤（方案 A）。"""

        await login_log.create(
            db_session,
            obj_in=LoginLogCreate(
                username="kw_login_success",
                ip="127.0.0.1",
                os="Windows",
                msg="ok",
                status=True,
            ),
        )
        await login_log.create(
            db_session,
            obj_in=LoginLogCreate(
                username="kw_login_fail",
                ip="127.0.0.2",
                os="Linux",
                msg="bad",
                status=False,
            ),
        )

        resp_success = await client.get(
            f"{settings.API_V1_STR}/logs/login",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "成功"},
        )
        assert resp_success.status_code == 200
        items_success = resp_success.json()["data"]["items"]
        assert items_success
        assert all(item["status"] is True for item in items_success)

        resp_fail = await client.get(
            f"{settings.API_V1_STR}/logs/login",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "失败"},
        )
        assert resp_fail.status_code == 200
        items_fail = resp_fail.json()["data"]["items"]
        assert items_fail
        assert all(item["status"] is False for item in items_fail)

    async def test_read_operation_logs(self, client: AsyncClient, auth_headers: dict):
        """测试获取操作日志"""
        response = await client.get(f"{settings.API_V1_STR}/logs/operation", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    async def test_read_operation_logs_keyword_response_code(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """测试操作日志 keyword 为数字时匹配状态码（方案 A）。"""

        await operation_log.create(
            db_session,
            obj_in=OperationLogCreate(
                username="kw_op_200",
                module="kw_module",
                ip="10.0.0.1",
                method="GET",
                response_code=200,
            ),
        )
        await operation_log.create(
            db_session,
            obj_in=OperationLogCreate(
                username="kw_op_500",
                module="kw_module",
                ip="10.0.0.2",
                method="POST",
                response_code=500,
            ),
        )

        resp_200 = await client.get(
            f"{settings.API_V1_STR}/logs/operation",
            headers=auth_headers,
            params={"page": 1, "page_size": 50, "keyword": "200"},
        )
        assert resp_200.status_code == 200
        items_200 = resp_200.json()["data"]["items"]
        assert items_200
        assert all(item.get("response_code") == 200 for item in items_200)
