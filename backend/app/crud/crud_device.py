"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_device.py
@DateTime: 2026-01-09 19:10:00
@Docs: 设备 CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


class CRUDDevice(CRUDBase[Device, DeviceCreate, DeviceUpdate]):
    """设备 CRUD 操作类。"""

    async def get(self, db: AsyncSession, id: UUID) -> Device | None:
        """
        通过 ID 获取设备（预加载部门关联）。
        """
        query = (
            select(self.model)
            .options(selectinload(Device.dept))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_ip(self, db: AsyncSession, ip_address: str) -> Device | None:
        """
        通过 IP 地址获取设备。

        Args:
            db: 数据库会话
            ip_address: IP 地址

        Returns:
            Device | None: 设备对象或 None
        """
        query = (
            select(self.model)
            .where(self.model.ip_address == ip_address)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def exists_ip(self, db: AsyncSession, ip_address: str, exclude_id: UUID | None = None) -> bool:
        """
        检查 IP 地址是否已存在。

        Args:
            db: 数据库会话
            ip_address: IP 地址
            exclude_id: 排除的设备ID（用于更新时排除自身）

        Returns:
            bool: IP 是否已存在
        """
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.ip_address == ip_address)
            .where(self.model.is_deleted.is_(False))
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_multi_paginated_filtered(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        vendor: str | None = None,
        status: str | None = None,
        device_group: str | None = None,
        dept_id: UUID | None = None,
    ) -> tuple[list[Device], int]:
        """
        获取分页过滤的设备列表。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键词（名称或IP）
            vendor: 厂商筛选
            status: 状态筛选
            device_group: 设备分组筛选
            dept_id: 部门筛选

        Returns:
            (items, total): 设备列表和总数
        """
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 基础查询
        base_query = select(self.model).where(self.model.is_deleted.is_(False))

        # 关键词搜索
        keyword = self._normalize_keyword(keyword)
        if keyword:
            base_query = base_query.where(
                or_(
                    self.model.name.ilike(f"%{keyword}%"),
                    self.model.ip_address.ilike(f"%{keyword}%"),
                )
            )

        # 厂商筛选
        if vendor:
            base_query = base_query.where(self.model.vendor == vendor)

        # 状态筛选
        if status:
            base_query = base_query.where(self.model.status == status)

        # 设备分组筛选
        if device_group:
            base_query = base_query.where(self.model.device_group == device_group)

        # 部门筛选
        if dept_id:
            base_query = base_query.where(self.model.dept_id == dept_id)

        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(Device.dept))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

    async def batch_create(
        self, db: AsyncSession, *, devices_in: list[DeviceCreate]
    ) -> tuple[list[Device], list[dict]]:
        """
        批量创建设备。

        Args:
            db: 数据库会话
            devices_in: 设备创建列表

        Returns:
            (created_devices, failed_items): 成功创建的设备列表和失败项
        """
        created_devices: list[Device] = []
        failed_items: list[dict] = []

        for device_in in devices_in:
            # 检查 IP 是否已存在
            if await self.exists_ip(db, device_in.ip_address):
                failed_items.append({
                    "ip_address": device_in.ip_address,
                    "name": device_in.name,
                    "reason": f"IP 地址 {device_in.ip_address} 已存在",
                })
                continue

            try:
                # 创建设备（排除 password 字段，由 Service 层处理加密）
                obj_data = device_in.model_dump(exclude={"password"}, exclude_unset=True)
                db_obj = self.model(**obj_data)
                db.add(db_obj)
                await db.flush()
                await db.refresh(db_obj)
                created_devices.append(db_obj)
            except Exception as e:
                failed_items.append({
                    "ip_address": device_in.ip_address,
                    "name": device_in.name,
                    "reason": str(e),
                })

        return created_devices, failed_items

    async def get_recycle_bin(
        self, db: AsyncSession, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Device], int]:
        """
        获取回收站中的设备。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量

        Returns:
            (items, total): 设备列表和总数
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 查询已删除的设备
        base_query = select(self.model).where(self.model.is_deleted.is_(True))

        # 计算总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        skip = (page - 1) * page_size
        items_query = (
            base_query.options(selectinload(Device.dept))
            .order_by(self.model.updated_at.desc())
            .offset(skip)
            .limit(page_size)
        )
        items_result = await db.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total


# 单例实例
device = CRUDDevice(Device)
