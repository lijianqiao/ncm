"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_topology.py
@DateTime: 2026-01-09 23:25:00
@Docs: 网络拓扑 (Topology) CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria

from app.crud.base import CRUDBase
from app.models.device import Device
from app.models.topology import TopologyLink
from app.schemas.topology import TopologyLinkCreate, TopologyLinkResponse


class CRUDTopology(CRUDBase[TopologyLink, TopologyLinkCreate, TopologyLinkResponse]):
    """网络拓扑 CRUD 类。"""

    @staticmethod
    def _upsert_set_clause(stmt):
        excluded = stmt.excluded
        return {
            "target_device_id": excluded.target_device_id,
            "target_interface": excluded.target_interface,
            "target_hostname": excluded.target_hostname,
            "target_ip": excluded.target_ip,
            "target_mac": excluded.target_mac,
            "target_description": excluded.target_description,
            "link_type": excluded.link_type,
            "link_speed": excluded.link_speed,
            "link_status": excluded.link_status,
            "collected_at": excluded.collected_at,
            "is_deleted": False,
            "updated_at": func.now(),
            "version_id": text("md5(random()::text)"),
        }

    async def upsert_many(self, db: AsyncSession, *, links_data: list[TopologyLinkCreate]) -> int:
        if not links_data:
            return 0

        values = [d.model_dump(exclude_unset=True) for d in links_data]
        stmt = insert(TopologyLink).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_device_id", "source_interface"],
            index_where=text("is_deleted = false"),
            set_=self._upsert_set_clause(stmt),
        )
        result = await db.execute(stmt)
        await db.flush()
        return int(getattr(result, "rowcount", 0) or 0)

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
        await self.upsert_many(db, links_data=[data])
        return await self.get_by_source_interface(
            db,
            source_device_id=data.source_device_id,
            source_interface=data.source_interface,
        )  # type: ignore[return-value]

    async def get_device_neighbors(self, db: AsyncSession, *, device_id: UUID) -> list[TopologyLink]:
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
            .options(with_loader_criteria(Device, Device.is_deleted.is_(False), include_aliases=True))
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

    async def get_all_links(self, db: AsyncSession, *, skip: int = 0, limit: int = 1000) -> list[TopologyLink]:
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
            .options(with_loader_criteria(Device, Device.is_deleted.is_(False), include_aliases=True))
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
        query = select(func.count()).select_from(self.model).where(self.model.is_deleted.is_(False))
        result = await db.execute(query)
        return result.scalar() or 0

    async def delete_device_links(self, db: AsyncSession, *, device_id: UUID, hard_delete: bool = False) -> int:
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
            result = await db.execute(
                update(self.model)
                .where(self.model.source_device_id == device_id, self.model.is_deleted.is_(False))
                .values(
                    is_deleted=True,
                    updated_at=func.now(),
                    version_id=text("md5(random()::text)"),
                )
            )
            await db.flush()
            return int(getattr(result, "rowcount", 0) or 0)

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
        await self.upsert_many(db, links_data=links_data)
        if not links_data:
            return []
        source_device_id = links_data[0].source_device_id
        return await self.get_device_neighbors(db, device_id=source_device_id)

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

        created_count = await self.upsert_many(db, links_data=links_data)
        return deleted_count, created_count

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
        query = query.options(with_loader_criteria(Device, Device.is_deleted.is_(False), include_aliases=True))
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
