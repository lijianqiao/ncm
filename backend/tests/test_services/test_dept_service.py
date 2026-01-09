"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_dept_service.py
@DateTime: 2026-01-08 00:00:00
@Docs: Dept Service 测试.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.crud.crud_dept import dept_crud
from app.schemas.dept import DeptCreate, DeptUpdate
from app.services.dept_service import DeptService


async def _create_dept_via_service(
    service: DeptService,
    *,
    name: str,
    code: str,
    parent_id=None,
    sort: int = 0,
    leader: str | None = None,
):
    return await service.create_dept(
        obj_in=DeptCreate(
            name=name,
            code=code,
            parent_id=parent_id,
            sort=sort,
            leader=leader,
            phone=None,
            email=None,
        )
    )


class TestDeptServiceTree:
    @pytest.mark.asyncio
    async def test_get_dept_tree_builds_and_sorts_and_excludes_deleted(self, db_session: AsyncSession):
        service = DeptService(db_session, dept_crud)

        root = await _create_dept_via_service(service, name="总部", code="HQ", leader="张三", sort=1)
        c1 = await _create_dept_via_service(service, name="测试", code="QA", leader="王五", parent_id=root.id, sort=2)
        c2 = await _create_dept_via_service(service, name="研发", code="RD", leader="李四", parent_id=root.id, sort=1)
        c3 = await _create_dept_via_service(service, name="已删", code="DEL", leader="X", parent_id=root.id, sort=3)

        # 手动软删除一个子部门
        deleted = await dept_crud.remove(db_session, id=c3.id)
        assert deleted is not None

        tree = await service.get_dept_tree()
        assert len(tree) == 1
        assert tree[0].id == root.id

        child_ids = [x.id for x in tree[0].children]
        assert child_ids == [c2.id, c1.id]
        assert c3.id not in child_ids

    @pytest.mark.asyncio
    async def test_get_dept_tree_keyword_search_leader(self, db_session: AsyncSession):
        service = DeptService(db_session, dept_crud)

        root = await _create_dept_via_service(service, name="总部", code="HQ", leader="张三", sort=1)
        child = await _create_dept_via_service(
            service, name="研发", code="RD", leader="李四", parent_id=root.id, sort=1
        )

        tree_root = await service.get_dept_tree(keyword="张三")
        assert len(tree_root) == 1
        assert tree_root[0].id == root.id

        tree_child = await service.get_dept_tree(keyword="李四")
        # 当前行为：SQL 先过滤，再构建树；若只命中子节点，子节点会成为根返回
        assert len(tree_child) == 1
        assert tree_child[0].id == child.id


class TestDeptServiceBusinessRules:
    @pytest.mark.asyncio
    async def test_create_dept_duplicate_code(self, db_session: AsyncSession):
        service = DeptService(db_session, dept_crud)

        await _create_dept_via_service(service, name="总部", code="HQ", leader="张三")
        with pytest.raises(BadRequestException):
            await _create_dept_via_service(service, name="总部2", code="HQ", leader="李四")

    @pytest.mark.asyncio
    async def test_update_dept_parent_cannot_be_self(self, db_session: AsyncSession):
        service = DeptService(db_session, dept_crud)

        dept = await _create_dept_via_service(service, name="总部", code="HQ", leader="张三")
        with pytest.raises(BadRequestException):
            await service.update_dept(dept_id=dept.id, obj_in=DeptUpdate(parent_id=dept.id))

    @pytest.mark.asyncio
    async def test_delete_dept_with_children_forbidden(self, db_session: AsyncSession):
        service = DeptService(db_session, dept_crud)

        root = await _create_dept_via_service(service, name="总部", code="HQ", leader="张三")
        await _create_dept_via_service(service, name="研发", code="RD", leader="李四", parent_id=root.id)

        with pytest.raises(BadRequestException):
            await service.delete_dept(dept_id=root.id)
