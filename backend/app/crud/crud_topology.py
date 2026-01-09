"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_topology.py
@DateTime: 2026-01-09 23:25:00
@Docs: 网络拓扑 (Topology) CRUD 操作。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.topology import TopologyLink
from app.schemas.topology import TopologyLinkCreate, TopologyLinkResponse


class CRUDTopology(CRUDBase[TopologyLink, TopologyLinkCreate, TopologyLinkResponse]):
    """网络拓扑 CRUD 类。"""

    async def get_by_source_interface(
        self,
        db: AsyncSession,
        *,
        source_device_id: UUID,
        source_interface: str,
    ) -> TopologyLink | None:
        """
        根据源设备和接口获取链路。

        Args:
            db: 数据库会话
            source_device_id: 源设备ID
            source_interface: 源接口名称

        Returns:
            TopologyLink 记录或 None
        """
        query = select(self.model).where(
            and_(
                self.model.source_device_id == source_device_id,
                self.model.source_interface == source_interface,
                self.model.is_deleted.is_(False),
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def upsert_link(
        self,
        db: AsyncSession,
        *,
        data: TopologyLinkCreate,
    ) -> TopologyLink:
        """
        创建或更新拓扑链路 (根据源设备+接口去重)。

        Args:
            db: 数据库会话
            data: 链路数据

        Returns:
            TopologyLink 记录
        """
        existing = await self.get_by_source_interface(
            db,
            source_device_id=data.source_device_id,
            source_interface=data.source_interface,
        )

        if existing:
            # 更新现有记录
            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(existing, field):
                    setattr(existing, field, value)

            db.add(existing)
            await db.flush()
            await db.refresh(existing)
            return existing
        else:
            # 创建新记录
            obj_data = data.model_dump(exclude_unset=True)
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            await db.flush()
            await db.refresh(db_obj)
            return db_obj

    async def get_device_neighbors(
        self, db: AsyncSession, *, device_id: UUID
    ) -> list[TopologyLink]:
        """
        获取设备的所有邻居链路。

        Args:
            db: 数据库会话
            device_id: 设备ID

        Returns:
            TopologyLink 列表
        """
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.source_device_id == device_id,
                    self.model.is_deleted.is_(False),
                )
            )
            .order_by(self.model.source_interface)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_all_links(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 1000
    ) -> list[TopologyLink]:
        """
        获取所有拓扑链路。

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 返回数量

        Returns:
            TopologyLink 列表
        """
        query = (
            select(self.model)
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def count_links(self, db: AsyncSession) -> int:
        """
        获取链路总数。

        Returns:
            链路总数
        """
        query = select(func.count()).select_from(self.model).where(
            self.model.is_deleted.is_(False)
        )
        result = await db.execute(query)
        return result.scalar() or 0

    async def delete_device_links(
        self, db: AsyncSession, *, device_id: UUID, hard_delete: bool = False
    ) -> int:
        """
        删除设备的所有链路 (用于刷新拓扑前)。

        Args:
            db: 数据库会话
            device_id: 设备ID
            hard_delete: 是否硬删除

        Returns:
            删除的链路数量
        """
        if hard_delete:
            # 硬删除
            query = delete(self.model).where(self.model.source_device_id == device_id)
            result = await db.execute(query)
            await db.flush()
            return result.rowcount  # type: ignore
        else:
            # 软删除
            links = await self.get_device_neighbors(db, device_id=device_id)
            count = 0
            for link in links:
                link.is_deleted = True
                db.add(link)
                count += 1
            await db.flush()
            return count

    async def batch_create_links(
        self,
        db: AsyncSession,
        *,
        links_data: list[TopologyLinkCreate],
    ) -> list[TopologyLink]:
        """
        批量创建拓扑链路。

        Args:
            db: 数据库会话
            links_data: 链路数据列表

        Returns:
            创建的 TopologyLink 列表
        """
        created_links = []
        for data in links_data:
            link = await self.upsert_link(db, data=data)
            created_links.append(link)
        return created_links

    async def refresh_device_topology(
        self,
        db: AsyncSession,
        *,
        device_id: UUID,
        links_data: list[TopologyLinkCreate],
    ) -> tuple[int, int]:
        """
        刷新设备拓扑 (删除旧链路，创建新链路)。

        Args:
            db: 数据库会话
            device_id: 设备ID
            links_data: 新的链路数据

        Returns:
            (deleted_count, created_count): 删除数量和创建数量
        """
        # 软删除旧链路
        deleted_count = await self.delete_device_links(db, device_id=device_id, hard_delete=False)

        # 创建新链路
        created_links = []
        for data in links_data:
            link = await self.upsert_link(db, data=data)
            created_links.append(link)

        return deleted_count, len(created_links)

    async def get_bidirectional_link(
        self,
        db: AsyncSession,
        *,
        device_a_id: UUID,
        device_b_id: UUID,
    ) -> list[TopologyLink]:
        """
        获取两个设备之间的双向链路。

        Args:
            db: 数据库会话
            device_a_id: 设备A ID
            device_b_id: 设备B ID

        Returns:
            TopologyLink 列表
        """
        query = select(self.model).where(
            and_(
                self.model.is_deleted.is_(False),
                or_(
                    and_(
                        self.model.source_device_id == device_a_id,
                        self.model.target_device_id == device_b_id,
                    ),
                    and_(
                        self.model.source_device_id == device_b_id,
                        self.model.target_device_id == device_a_id,
                    ),
                ),
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_unique_devices_in_topology(self, db: AsyncSession) -> set[UUID]:
        """
        获取拓扑中涉及的所有设备ID。

        Returns:
            设备ID集合
        """
        query = (
            select(self.model.source_device_id, self.model.target_device_id)
            .where(self.model.is_deleted.is_(False))
            .distinct()
        )
        result = await db.execute(query)
        rows = result.all()

        device_ids: set[UUID] = set()
        for source_id, target_id in rows:
            device_ids.add(source_id)
            if target_id:
                device_ids.add(target_id)

        return device_ids


# 创建单例实例
topology_crud = CRUDTopology(TopologyLink)
