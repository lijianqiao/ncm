"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_depts.py
@DateTime: 2026-01-08 00:00:00
@Docs: Dept API 接口测试.
"""

import pytest
from httpx import AsyncClient

from app.core.config import settings


async def _create_dept_api(
    client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    code: str,
    parent_id: str | None = None,
    sort: int = 0,
    leader: str | None = None,
):
    payload = {
        "name": name,
        "code": code,
        "parent_id": parent_id,
        "sort": sort,
        "leader": leader,
        "phone": None,
        "email": None,
    }
    res = await client.post(f"{settings.API_V1_STR}/depts/", headers=auth_headers, json=payload)
    assert res.status_code == 200, res.text
    return res.json()["data"]


class TestDeptApiRead:
    @pytest.mark.asyncio
    async def test_get_dept_tree_keyword_search(self, client: AsyncClient, auth_headers: dict[str, str]):
        d = await _create_dept_api(client, auth_headers, name="总部", code="HQ", leader="张三", sort=1)

        res = await client.get(
            f"{settings.API_V1_STR}/depts/tree",
            headers=auth_headers,
            params={"keyword": "张三"},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert isinstance(data, list)
        assert any(x["id"] == d["id"] for x in data)

    @pytest.mark.asyncio
    async def test_read_depts_paginated_keyword_three_fields(self, client: AsyncClient, auth_headers: dict[str, str]):
        d = await _create_dept_api(client, auth_headers, name="总部", code="HQ", leader="张三", sort=1)

        for kw in ["总部", "HQ", "张三"]:
            res = await client.get(
                f"{settings.API_V1_STR}/depts/",
                headers=auth_headers,
                params={"page": 1, "page_size": 50, "keyword": kw},
            )
            assert res.status_code == 200, res.text
            items = res.json()["data"]["items"]
            assert any(x["id"] == d["id"] for x in items)


class TestDeptApiRecycleAndBatch:
    @pytest.mark.asyncio
    async def test_batch_delete_and_batch_restore(self, client: AsyncClient, auth_headers: dict[str, str]):
        d1 = await _create_dept_api(client, auth_headers, name="总部", code="HQ", leader="张三", sort=1)
        d2 = await _create_dept_api(client, auth_headers, name="分部", code="BR", leader="赵六", sort=2)

        # Batch delete（验证路由不会被 /{id} 抢走）
        res = await client.request(
            "DELETE",
            f"{settings.API_V1_STR}/depts/batch",
            headers=auth_headers,
            json={"ids": [d1["id"], d2["id"]], "hard_delete": False},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["success_count"] == 2

        # Recycle bin should contain
        res = await client.get(f"{settings.API_V1_STR}/depts/recycle-bin", headers=auth_headers)
        assert res.status_code == 200, res.text
        items = res.json()["data"]["items"]
        assert any(x["id"] == d1["id"] for x in items)
        assert any(x["id"] == d2["id"] for x in items)

        # Batch restore
        res = await client.post(
            f"{settings.API_V1_STR}/depts/batch/restore",
            headers=auth_headers,
            json={"ids": [d1["id"], d2["id"]]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["success_count"] == 2
        assert res.json()["data"]["failed_ids"] == []

        # Verify NOT in recycle bin
        res = await client.get(f"{settings.API_V1_STR}/depts/recycle-bin", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert not any(x["id"] == d1["id"] for x in items)
        assert not any(x["id"] == d2["id"] for x in items)
