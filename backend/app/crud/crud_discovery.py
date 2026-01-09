"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_discovery.py
@DateTime: 2026-01-09 23:20:00
@Docs: 设备发现 (Discovery) CRUD 操作。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DiscoveryStatus
from app.crud.base import CRUDBase
from app.models.discovery import Discovery
from app.schemas.discovery import DiscoveryCreate, DiscoveryUpdate


class CRUDDiscovery(CRUDBase[Discovery, DiscoveryCreate, DiscoveryUpdate]):
    """设备发现 CRUD 类。"""

    async def get_by_ip(self, db: AsyncSession, *, ip_address: str) -> Discovery | None:
        """
        根据 IP 地址获取发现记录。

        Args:
            db: 数据库会话
            ip_address: IP 地址

        Returns:
            Discovery 记录或 None
        """
        query = select(self.model).where(
            and_(
                self.model.ip_address == ip_address,
                self.model.is_deleted.is_(False),
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def upsert_discovery(
        self,
        db: AsyncSession,
        *,
        data: DiscoveryCreate,
        scan_source: str | None = None,
        scan_task_id: str | None = None,
    ) -> Discovery:
        """
        创建或更新发现记录 (根据 IP 地址去重)。

        Args:
            db: 数据库会话
            data: 发现数据
            scan_source: 扫描来源
            scan_task_id: 扫描任务ID

        Returns:
            Discovery 记录
        """
        now = datetime.now()
        existing = await self.get_by_ip(db, ip_address=data.ip_address)

        if existing:
            # 更新现有记录
            update_data = data.model_dump(exclude_unset=True)
            update_data["last_seen_at"] = now
            update_data["offline_days"] = 0
            if scan_source:
                update_data["scan_source"] = scan_source
            if scan_task_id:
                update_data["scan_task_id"] = scan_task_id

            for field, value in update_data.items():
                if hasattr(existing, field) and value is not None:
                    setattr(existing, field, value)

            db.add(existing)
            await db.flush()
            await db.refresh(existing)
            return existing
        else:
            # 创建新记录
            obj_data = data.model_dump(exclude_unset=True)
            obj_data["first_seen_at"] = now
            obj_data["last_seen_at"] = now
            obj_data["status"] = DiscoveryStatus.PENDING.value
            if scan_source:
                obj_data["scan_source"] = scan_source
            if scan_task_id:
                obj_data["scan_task_id"] = scan_task_id

            db_obj = self.model(**obj_data)
            db.add(db_obj)
            await db.flush()
            await db.refresh(db_obj)
            return db_obj

    async def get_shadow_assets(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[Discovery]:
        """
        获取影子资产列表 (未在 CMDB 中的发现设备)。

        Args:
            db: 数据库会话
            skip: 跳过数量
            limit: 返回数量

        Returns:
            Discovery 列表
        """
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.status == DiscoveryStatus.SHADOW.value,
                    self.model.is_deleted.is_(False),
                )
            )
            .order_by(self.model.last_seen_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_offline_records(
        self, db: AsyncSession, *, min_offline_days: int = 1, skip: int = 0, limit: int = 100
    ) -> list[Discovery]:
        """
        获取离线记录列表。

        Args:
            db: 数据库会话
            min_offline_days: 最小离线天数
            skip: 跳过数量
            limit: 返回数量

        Returns:
            Discovery 列表
        """
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.offline_days >= min_offline_days,
                    self.model.is_deleted.is_(False),
                )
            )
            .order_by(self.model.offline_days.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: DiscoveryStatus | None = None,
        keyword: str | None = None,
        scan_source: str | None = None,
    ) -> tuple[list[Discovery], int]:
        """
        分页查询发现记录，支持筛选。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            status: 状态筛选
            keyword: 关键词搜索 (IP/主机名)
            scan_source: 扫描来源筛选

        Returns:
            (items, total): 数据列表和总数
        """
        # 基础查询条件
        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]

        # 状态筛选
        if status:
            conditions.append(self.model.status == status.value)

        # 关键词搜索
        keyword = self._normalize_keyword(keyword)
        if keyword:
            conditions.append(
                or_(
                    self.model.ip_address.ilike(f"%{keyword}%"),
                    self.model.hostname.ilike(f"%{keyword}%"),
                    self.model.mac_address.ilike(f"%{keyword}%"),
                )
            )

        # 扫描来源筛选
        if scan_source:
            conditions.append(self.model.scan_source == scan_source)

        # 构建查询
        base_query = select(self.model).where(and_(*conditions))

        # 查询总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        skip = (page - 1) * page_size
        query = base_query.order_by(self.model.last_seen_at.desc()).offset(skip).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_status(self, db: AsyncSession, *, id: UUID, status: DiscoveryStatus) -> Discovery | None:
        """
        更新发现记录状态。

        Args:
            db: 数据库会话
            id: 记录ID
            status: 新状态

        Returns:
            更新后的 Discovery 记录或 None
        """
        obj = await self.get(db, id=id)
        if obj:
            obj.status = status.value
            db.add(obj)
            await db.flush()
            await db.refresh(obj)
        return obj

    async def set_matched_device(self, db: AsyncSession, *, id: UUID, device_id: UUID) -> Discovery | None:
        """
        设置发现记录的匹配设备。

        Args:
            db: 数据库会话
            id: 发现记录ID
            device_id: 匹配的设备ID

        Returns:
            更新后的 Discovery 记录或 None
        """
        obj = await self.get(db, id=id)
        if obj:
            obj.matched_device_id = device_id
            obj.status = DiscoveryStatus.MATCHED.value
            db.add(obj)
            await db.flush()
            await db.refresh(obj)
        return obj

    async def increment_offline_days(self, db: AsyncSession) -> int:
        """
        将所有未更新的发现记录离线天数加1。

        Returns:
            更新的记录数量
        """
        # 获取所有非离线状态且非删除的记录
        query = select(self.model).where(
            and_(
                self.model.is_deleted.is_(False),
                self.model.status != DiscoveryStatus.OFFLINE.value,
            )
        )
        result = await db.execute(query)
        records = result.scalars().all()

        count = 0
        for record in records:
            record.offline_days += 1
            db.add(record)
            count += 1

        await db.flush()
        return count


# 创建单例实例
discovery_crud = CRUDDiscovery(Discovery)
