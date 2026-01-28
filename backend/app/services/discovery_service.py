"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: discovery_service.py
@DateTime: 2026-01-15 00:00:00
@Docs: 设备发现（Discovery）业务服务。
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.enums import DiscoveryStatus
from app.core.exceptions import NotFoundException
from app.crud.crud_discovery import CRUDDiscovery
from app.models.discovery import Discovery


class DiscoveryService:
    def __init__(self, db: AsyncSession, discovery_crud: CRUDDiscovery):
        self.db = db
        self.discovery_crud = discovery_crud

    async def get_discoveries_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: DiscoveryStatus | None = None,
        keyword: str | None = None,
        scan_source: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[Discovery], int]:
        from app.models.discovery import Discovery

        order_expr = self._build_sort_expression(Discovery, sort_by, sort_order)
        return await self.discovery_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            max_size=10000,
            keyword=keyword,
            keyword_columns=[Discovery.ip_address, Discovery.hostname, Discovery.mac_address],
            order_by=order_expr,
            status=status.value if status else None,
            scan_source=scan_source,
        )

    @staticmethod
    def _build_sort_expression(model, sort_by: str | None, sort_order: str | None):
        """构建排序表达式。"""
        sort_by_normalized = (sort_by or "").strip()
        sort_order_normalized = (sort_order or "").strip().lower()

        sort_map = {
            "ip_address": model.ip_address,
            "mac_address": model.mac_address,
            "vendor": model.vendor,
            "hostname": model.hostname,
            "os_info": model.os_info,
            "status": model.status,
            "scan_source": model.scan_source,
            "first_seen_at": model.first_seen_at,
            "last_seen_at": model.last_seen_at,
            "offline_days": model.offline_days,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

        sort_col = sort_map.get(sort_by_normalized, model.last_seen_at)
        if sort_order_normalized not in {"asc", "desc"}:
            sort_order_normalized = "desc"

        return sort_col.asc() if sort_order_normalized == "asc" else sort_col.desc()

    async def get_deleted_discoveries_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: DiscoveryStatus | None = None,
        keyword: str | None = None,
        scan_source: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[Discovery], int]:
        from app.models.discovery import Discovery

        order_expr = self._build_sort_expression(Discovery, sort_by, sort_order)
        return await self.discovery_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            max_size=10000,
            keyword=keyword,
            keyword_columns=[Discovery.ip_address, Discovery.hostname, Discovery.mac_address],
            order_by=order_expr,
            is_deleted=True,
            status=status.value if status else None,
            scan_source=scan_source,
        )

    async def get_discovery(self, *, discovery_id: UUID) -> Discovery:
        discovery = await self.discovery_crud.get(self.db, id=discovery_id)
        if not discovery:
            raise NotFoundException(message="发现记录不存在")
        return discovery

    @transactional()
    async def delete_discovery(self, *, discovery_id: UUID) -> Discovery:
        discovery = await self.get_discovery(discovery_id=discovery_id)
        success_count, _ = await self.discovery_crud.batch_remove(self.db, ids=[discovery_id], hard_delete=False)
        if success_count == 0:
            raise NotFoundException(message="删除失败")
        return discovery

    @transactional()
    async def batch_delete_discoveries(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        return await self.discovery_crud.batch_remove(self.db, ids=ids, hard_delete=False)

    @transactional()
    async def restore_discovery(self, *, discovery_id: UUID) -> Discovery:
        success_count, failed_ids = await self.discovery_crud.batch_restore(self.db, ids=[discovery_id])
        if success_count == 0:
            raise NotFoundException(message="发现记录不存在或未被删除")
        if failed_ids:
            raise NotFoundException(message="恢复失败")
        discovery = await self.discovery_crud.get(self.db, id=discovery_id)
        if not discovery:
            raise NotFoundException(message="恢复失败")
        return discovery

    @transactional()
    async def batch_restore_discoveries(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        return await self.discovery_crud.batch_restore(self.db, ids=ids)

    @transactional()
    async def hard_delete_discovery(self, *, discovery_id: UUID) -> None:
        stmt = select(Discovery.id).where(Discovery.id == discovery_id, Discovery.is_deleted.is_(True))
        exists = (await self.db.execute(stmt)).scalars().first()
        if exists is None:
            raise NotFoundException(message="发现记录不存在或未被软删除")

        success_count, _ = await self.discovery_crud.batch_remove(self.db, ids=[discovery_id], hard_delete=True)
        if success_count == 0:
            raise NotFoundException(message="彻底删除失败")

    @transactional()
    async def batch_hard_delete_discoveries(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        return await self.discovery_crud.batch_remove(self.db, ids=ids, hard_delete=True)
