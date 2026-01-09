"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_dept.py
@DateTime: 2026-01-08 00:00:00
@Docs: Dept Schemas 测试.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.dept import DeptCreate, DeptResponse, DeptUpdate


class TestDeptSchemas:
    def test_dept_create_validation(self):
        with pytest.raises(ValidationError):
            DeptCreate(name="", code="HQ")

        with pytest.raises(ValidationError):
            DeptCreate(name="总部", code="")

        obj = DeptCreate(name="总部", code="HQ")
        assert obj.name == "总部"
        assert obj.code == "HQ"

        with pytest.raises(ValidationError):
            DeptCreate(name="总部", code="HQ", phone="12345")

    def test_dept_update_optional(self):
        obj = DeptUpdate()
        assert obj.model_dump(exclude_unset=True) == {}

    def test_dept_response_children_default_not_shared(self):
        now = datetime.now(UTC)
        d1 = DeptResponse(
            id=uuid4(),
            name="总部",
            code="HQ",
            parent_id=None,
            sort=0,
            leader=None,
            phone=None,
            email=None,
            is_active=True,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        d2 = DeptResponse(
            id=uuid4(),
            name="分部",
            code="BR",
            parent_id=None,
            sort=0,
            leader=None,
            phone=None,
            email=None,
            is_active=True,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        d1.children.append(d2)
        assert len(d1.children) == 1
        assert d2.children == []
