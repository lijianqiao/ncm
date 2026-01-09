"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: inventory_audit_service.py
@DateTime: 2026-01-09 21:25:00
@Docs: 资产盘点任务服务。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import InventoryAuditStatus
from app.core.exceptions import NotFoundException
from app.crud.crud_inventory_audit import CRUDInventoryAudit
from app.models.inventory_audit import InventoryAudit
from app.schemas.inventory_audit import InventoryAuditCreate


class InventoryAuditService:
    def __init__(self, db: AsyncSession, inventory_audit_crud: CRUDInventoryAudit):
        self.db = db
        self.inventory_audit_crud = inventory_audit_crud

    async def get(self, audit_id: UUID) -> InventoryAudit:
        audit = await self.inventory_audit_crud.get(self.db, id=audit_id)
        if not audit:
            raise NotFoundException(message="盘点任务不存在")
        return audit

    async def list_paginated(self, *, page: int = 1, page_size: int = 20, status: str | None = None):
        return await self.inventory_audit_crud.get_multi_paginated_filtered(
            self.db, page=page, page_size=page_size, status=status
        )

    @transactional()
    async def create(self, data: InventoryAuditCreate, *, operator_id: UUID | None) -> InventoryAudit:
        obj = InventoryAudit(
            name=data.name,
            scope=data.scope.model_dump(),
            status=InventoryAuditStatus.PENDING.value,
            operator_id=operator_id,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @transactional()
    async def bind_celery_task(self, audit_id: UUID, celery_task_id: str) -> InventoryAudit:
        audit = await self.get(audit_id)
        audit.celery_task_id = celery_task_id
        audit.status = InventoryAuditStatus.RUNNING.value
        audit.started_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(audit)
        return audit

