"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_topology.py
@DateTime: 2026-01-09 23:25:00
@Docs: 网络拓扑 (Topology) CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import delete, func, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.topology import TopologyLink
from app.schemas.topology import TopologyLinkCreate, TopologyLinkResponse


class CRUDTopology(CRUDBase[TopologyLink, TopologyLinkCreate, TopologyLinkResponse]):
    """网络拓扑 CRUD 类（纯数据访问）。"""

    @staticmethod
    def _upsert_set_clause(stmt):
        """构建 upsert 更新字段。"""
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
        """
        批量 upsert 链路数据。

        Args:
            db: 数据库会话
            links_data: 链路数据列表

        Returns:
            受影响的行数
        """
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

    async def delete_by_device(self, db: AsyncSession, *, device_id: UUID, hard_delete: bool = False) -> int:
        """
        删除指定设备的所有链路。

        Args:
            db: 数据库会话
            device_id: 设备ID
            hard_delete: 是否硬删除

        Returns:
            删除的链路数量
        """
        if hard_delete:
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

    async def delete_all(self, db: AsyncSession, *, hard_delete: bool = False) -> int:
        """
        删除所有链路。

        Args:
            db: 数据库会话
            hard_delete: 是否硬删除

        Returns:
            删除的链路数量
        """
        if hard_delete:
            result = await db.execute(delete(self.model))
            await db.flush()
            return result.rowcount  # type: ignore
        else:
            result = await db.execute(
                update(self.model)
                .where(self.model.is_deleted.is_(False))
                .values(
                    is_deleted=True,
                    updated_at=func.now(),
                    version_id=text("md5(random()::text)"),
                )
            )
            await db.flush()
            return int(getattr(result, "rowcount", 0) or 0)


# 创建单例实例
topology_crud = CRUDTopology(TopologyLink)
