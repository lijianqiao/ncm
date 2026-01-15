"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_crud_dept.py
@DateTime: 2026-01-08 00:00:00
@Docs: Dept CRUD 测试.
"""

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.crud.crud_dept import dept_crud
from app.models.dept import Department
from app.models.user import User
from app.schemas.dept import DeptCreate


async def _create_dept(
    db_session: AsyncSession,
    *,
    name: str,
    code: str,
    parent_id=None,
    sort: int = 0,
    leader: str | None = None,
    is_active: bool | None = None,
) -> Department:
    dept_in = DeptCreate(
        name=name,
        code=code,
        parent_id=parent_id,
        sort=sort,
        leader=leader,
        phone=None,
        email=None,
    )
    dept = await dept_crud.create(db_session, obj_in=dept_in)
    if is_active is not None:
        await db_session.execute(update(Department).where(Department.id == dept.id).values(is_active=is_active))
        await db_session.commit()
        dept = await dept_crud.get(db_session, id=dept.id)
        assert dept is not None
    return dept


class TestCRUDDeptGetMultiPaginated:
    async def test_keyword_search_name_code_leader(self, db_session: AsyncSession):
        dept = await _create_dept(db_session, name="总部", code="HQ", leader="张三", sort=1)
        await _create_dept(db_session, name="分部", code="BR", leader="赵六", sort=2)

        items, total = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, keyword="总部")
        assert total == 1
        assert any(x.id == dept.id for x in items)

        items, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, keyword="HQ")
        assert any(x.id == dept.id for x in items)

        items, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, keyword="张三")
        assert any(x.id == dept.id for x in items)

        items, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, keyword="不存在")
        assert items == []

    async def test_filter_is_active(self, db_session: AsyncSession):
        d1 = await _create_dept(db_session, name="启用部门", code="ACTIVE", leader="A", is_active=True)
        d2 = await _create_dept(db_session, name="禁用部门", code="INACTIVE", leader="B", is_active=False)

        items, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, is_active=True)
        ids = {x.id for x in items}
        assert d1.id in ids
        assert d2.id not in ids


class TestCRUDDeptTree:
    async def test_get_tree_includes_all_and_keyword(self, db_session: AsyncSession):
        root = await _create_dept(db_session, name="总部", code="HQ", leader="张三", sort=1)
        child = await _create_dept(db_session, name="研发", code="RD", leader="李四", parent_id=root.id, sort=1)

        depts = await dept_crud.get_tree(db_session)
        ids = {d.id for d in depts}
        assert root.id in ids
        assert child.id in ids

        depts_kw = await dept_crud.get_tree(db_session, keyword="研发")
        ids_kw = {d.id for d in depts_kw}
        assert child.id in ids_kw
        assert root.id not in ids_kw


class TestCRUDDeptHelpers:
    async def test_exists_code_with_exclude(self, db_session: AsyncSession):
        dept = await _create_dept(db_session, name="总部", code="HQ", leader="张三")
        assert await dept_crud.exists_code(db_session, code="HQ") is True
        assert await dept_crud.exists_code(db_session, code="HQ", exclude_id=dept.id) is False

    async def test_has_children_and_get_children_ids(self, db_session: AsyncSession):
        root = await _create_dept(db_session, name="总部", code="HQ", leader="张三")
        child = await _create_dept(db_session, name="研发", code="RD", leader="李四", parent_id=root.id)

        assert await dept_crud.has_children(db_session, dept_id=root.id) is True
        assert await dept_crud.has_children(db_session, dept_id=child.id) is False

        ids = await dept_crud.get_children_ids(db_session, dept_id=root.id)
        assert child.id in ids

    async def test_has_users(self, db_session: AsyncSession):
        dept = await _create_dept(db_session, name="总部", code="HQ", leader="张三")
        user = User(
            username="dept_user",
            password=get_password_hash("Test@123456"),
            email="dept_user@example.com",
            phone="+8613800138011",
            nickname="部门用户",
            is_active=True,
            is_superuser=False,
            dept_id=dept.id,
        )
        db_session.add(user)
        await db_session.commit()

        assert await dept_crud.has_users(db_session, dept_id=dept.id) is True


@pytest.mark.asyncio
async def test_soft_delete_excluded_by_default(db_session: AsyncSession):
    dept = await _create_dept(db_session, name="总部", code="HQ", leader="张三")
    success_count, failed_ids = await dept_crud.batch_remove(db_session, ids=[dept.id])
    assert success_count == 1
    assert failed_ids == []

    items, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50)
    assert not any(x.id == dept.id for x in items)

    items_deleted, _ = await dept_crud.get_multi_paginated(db_session, page=1, page_size=50, include_deleted=True)
    assert any(x.id == dept.id for x in items_deleted)
    assert next(x for x in items_deleted if x.id == dept.id).is_deleted is True
