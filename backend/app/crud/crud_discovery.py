"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_discovery.py
@DateTime: 2026-01-09 23:20:00
@Docs: 设备发现 (Discovery) CRUD 操作。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

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

    async def upsert_many(
        self,
        db: AsyncSession,
        *,
        data_list: list[DiscoveryCreate],
        scan_source: str | None = None,
        scan_task_id: str | None = None,
    ) -> int:
        """批量创建或更新发现记录（按 IP 去重）。

        说明：该方法针对扫描入库场景优化，避免逐条 get_by_ip + flush + refresh。

        Args:
            db: 数据库会话
            data_list: 待写入的发现数据列表
            scan_source: 扫描来源
            scan_task_id: 扫描任务ID

        Returns:
            实际处理的记录数
        """
        if not data_list:
            return 0

        now = datetime.now()
        ips = list({d.ip_address for d in data_list})

        query = select(self.model).where(
            and_(
                self.model.ip_address.in_(ips),
                self.model.is_deleted.is_(False),
            )
        )
        result = await db.execute(query)
        existing_list = list(result.scalars().all())
        existing_map: dict[str, Discovery] = {d.ip_address: d for d in existing_list}

        created = 0
        updated = 0

        for data in data_list:
            existing = existing_map.get(data.ip_address)

            if existing:
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
                updated += 1
                continue

            obj_data = data.model_dump(exclude_unset=True)
            obj_data["first_seen_at"] = now
            obj_data["last_seen_at"] = now
            obj_data["offline_days"] = 0
            obj_data["status"] = DiscoveryStatus.PENDING.value
            if scan_source:
                obj_data["scan_source"] = scan_source
            if scan_task_id:
                obj_data["scan_task_id"] = scan_task_id

            db_obj = self.model(**obj_data)
            db.add(db_obj)
            existing_map[data.ip_address] = db_obj
            created += 1

        await db.flush()
        return created + updated

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

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: DiscoveryStatus | None = None,
        keyword: str | None = None,
        scan_source: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
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
        page, page_size = self._validate_pagination(page, page_size)

        # 基础查询条件
        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]

        # 状态筛选
        if status:
            conditions.append(self.model.status == status.value)

        # 关键词搜索
        keyword_clause = self._or_ilike_contains(
            keyword, [self.model.ip_address, self.model.hostname, self.model.mac_address]
        )
        if keyword_clause is not None:
            conditions.append(keyword_clause)

        # 扫描来源筛选
        if scan_source:
            conditions.append(self.model.scan_source == scan_source)

        # 排序
        sort_by = (sort_by or "").strip()
        sort_order = (sort_order or "").strip().lower()
        sort_map = {
            "ip_address": self.model.ip_address,
            "mac_address": self.model.mac_address,
            "vendor": self.model.vendor,
            "hostname": self.model.hostname,
            "os_info": self.model.os_info,
            "status": self.model.status,
            "scan_source": self.model.scan_source,
            "first_seen_at": self.model.first_seen_at,
            "last_seen_at": self.model.last_seen_at,
            "offline_days": self.model.offline_days,
            "created_at": self.model.created_at,
            "updated_at": self.model.updated_at,
        }
        sort_col = sort_map.get(sort_by) if sort_by else None
        if sort_col is None:
            sort_col = self.model.last_seen_at
            sort_order = "desc"
        if sort_order not in {"asc", "desc"}:
            sort_order = "desc"

        where_clause = self._and_where(conditions)
        count_stmt = select(func.count(Discovery.id)).where(where_clause)

        order_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()
        stmt = select(self.model).where(where_clause).order_by(order_expr)
        return await self.paginate(
            db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size, max_size=10000, default_size=20
        )

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
        result = await db.execute(
            update(self.model)
            .where(
                self.model.is_deleted.is_(False),
                self.model.status != DiscoveryStatus.OFFLINE.value,
            )
            .values(offline_days=self.model.offline_days + 1)
        )
        await db.flush()
        return int(getattr(result, "rowcount", 0) or 0)


# 创建单例实例
discovery_crud = CRUDDiscovery(Discovery)
