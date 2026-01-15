"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_inventory_audit.py
@DateTime: 2026-01-09 21:20:00
@Docs: InventoryAudit CRUD。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.inventory_audit import InventoryAudit
from app.schemas.inventory_audit import InventoryAuditCreate


class CRUDInventoryAudit(CRUDBase[InventoryAudit, InventoryAuditCreate, InventoryAuditCreate]):
    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[InventoryAudit], int]:
        stmt = select(InventoryAudit)
        count_stmt = select(func.count(InventoryAudit.id))

        if status:
            stmt = stmt.where(InventoryAudit.status == status)
            count_stmt = count_stmt.where(InventoryAudit.status == status)

        stmt = stmt.order_by(InventoryAudit.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        total = await db.scalar(count_stmt) or 0
        items = (await db.execute(stmt)).scalars().all()
        return list(items), int(total)


inventory_audit_crud = CRUDInventoryAudit(InventoryAudit)

