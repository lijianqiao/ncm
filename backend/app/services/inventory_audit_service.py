"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: inventory_audit_service.py
@DateTime: 2026-01-09 21:25:00
@Docs: 资产盘点任务服务。
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
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
        return await self.inventory_audit_crud.get_multi_paginated(
            self.db, page=page, page_size=page_size, status=status
        )

    async def list_deleted_paginated(self, *, page: int = 1, page_size: int = 20, status: str | None = None):
        return await self.inventory_audit_crud.get_multi_deleted_paginated(
            self.db, page=page, page_size=page_size, status=status
        )

    @transactional()
    async def delete(self, audit_id: UUID) -> InventoryAudit:
        audit = await self.get(audit_id)
        success_count, failed_ids = await self.inventory_audit_crud.batch_remove(self.db, ids=[audit_id], hard_delete=False)
        if success_count == 0 or failed_ids:
            raise NotFoundException(message="删除失败")
        return audit

    @transactional()
    async def batch_delete(self, *, ids: list[UUID], hard_delete: bool = False) -> tuple[int, list[UUID]]:
        return await self.inventory_audit_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)

    @transactional()
    async def restore(self, audit_id: UUID) -> InventoryAudit:
        success_count, failed_ids = await self.inventory_audit_crud.batch_restore(self.db, ids=[audit_id])
        if success_count == 0 or failed_ids:
            raise NotFoundException(message="盘点任务不存在或未被删除")
        audit = await self.inventory_audit_crud.get(self.db, id=audit_id)
        if not audit:
            raise NotFoundException(message="恢复失败")
        return audit

    @transactional()
    async def batch_restore(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        return await self.inventory_audit_crud.batch_restore(self.db, ids=ids)

    @transactional()
    async def hard_delete(self, audit_id: UUID) -> None:
        stmt = select(InventoryAudit.id).where(InventoryAudit.id == audit_id, InventoryAudit.is_deleted.is_(True))
        exists = (await self.db.execute(stmt)).scalars().first()
        if exists is None:
            raise NotFoundException(message="盘点任务不存在或未被软删除")
        success_count, failed_ids = await self.batch_delete(ids=[audit_id], hard_delete=True)
        if success_count == 0 or failed_ids:
            raise NotFoundException(message="彻底删除失败")

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

