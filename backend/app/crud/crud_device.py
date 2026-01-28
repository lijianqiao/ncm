"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_device.py
@DateTime: 2026-01-09 19:10:00
@Docs: 设备 CRUD 操作。
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.crud.base import CRUDBase
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


class CRUDDevice(CRUDBase[Device, DeviceCreate, DeviceUpdate]):
    """设备 CRUD 操作类。"""

    # 设备关联加载选项
    _DEVICE_OPTIONS = [selectinload(Device.dept)]

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> Device | None:
        """通过 ID 获取设备（预加载部门关联）。"""
        return await super().get(db, id, is_deleted=is_deleted, options=options or self._DEVICE_OPTIONS)

    async def get_by_ip(self, db: AsyncSession, ip_address: str) -> Device | None:
        """
        通过 IP 地址获取设备。

        Args:
            db: 数据库会话
            ip_address: IP 地址

        Returns:
            Device | None: 设备对象或 None
        """
        query = select(self.model).where(self.model.ip_address == ip_address).where(self.model.is_deleted.is_(False))
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str) -> Device | None:
        """
        通过设备名称精确匹配获取设备。

        Args:
            db: 数据库会话
            name: 设备名称

        Returns:
            Device | None: 设备对象或 None
        """
        query = select(self.model).where(self.model.name == name).where(self.model.is_deleted.is_(False))
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_name_like(self, db: AsyncSession, name: str) -> Device | None:
        """
        通过设备名称模糊匹配获取设备（前缀匹配或包含匹配）。

        匹配逻辑：
        1. 如果 CMDB 设备名称以 LLDP 上报的 hostname 开头，则匹配成功
        2. 如果 LLDP 上报的 hostname 以 CMDB 设备名称开头，则匹配成功

        例如：
        - LLDP: "SW-Core-01" 可匹配 CMDB: "SW-Core-01-BJ"
        - LLDP: "SW-Core-01.domain.local" 可匹配 CMDB: "SW-Core-01"

        Args:
            db: 数据库会话
            name: 设备名称（通常是 LLDP 上报的 hostname）

        Returns:
            Device | None: 设备对象或 None（返回第一个匹配项）
        """
        if not name:
            return None

        # 1. 尝试 CMDB 名称以 LLDP hostname 开头
        query = (
            select(self.model)
            .where(self.model.name.ilike(f"{name}%"))
            .where(self.model.is_deleted.is_(False))
            .limit(1)
        )
        result = await db.execute(query)
        device = result.scalars().first()
        if device:
            return device

        # 2. 尝试 LLDP hostname 以 CMDB 名称开头（反向匹配）
        # 通过获取可能匹配的设备列表，然后在应用层筛选
        # 由于 SQL 难以表达 "LLDP hostname 以 CMDB name 开头"，这里简化处理
        # 取 hostname 的主要部分（去掉域名后缀）进行匹配
        name_parts = name.split(".")
        if len(name_parts) > 1:
            short_name = name_parts[0]
            query = (
                select(self.model)
                .where(self.model.name == short_name)
                .where(self.model.is_deleted.is_(False))
                .limit(1)
            )
            result = await db.execute(query)
            return result.scalars().first()

        return None

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

        if not devices_in:
            return created_devices, failed_items

        ips = list({d.ip_address for d in devices_in})
        existing_ips = set(
            (
                await db.execute(
                    select(Device.ip_address).where(Device.ip_address.in_(ips), Device.is_deleted.is_(False))
                )
            )
            .scalars()
            .all()
        )

        for device_in in devices_in:
            if device_in.ip_address in existing_ips:
                failed_items.append(
                    {
                        "ip_address": device_in.ip_address,
                        "name": device_in.name,
                        "reason": f"IP 地址 {device_in.ip_address} 已存在",
                    }
                )
                continue

            try:
                async with db.begin_nested():
                    obj_data = device_in.model_dump(exclude={"password"}, exclude_unset=True)
                    db_obj = self.model(**obj_data)
                    db.add(db_obj)
                    await db.flush()
                    await db.refresh(db_obj)
                    created_devices.append(db_obj)
                    existing_ips.add(device_in.ip_address)
            except Exception as e:
                failed_items.append(
                    {
                        "ip_address": device_in.ip_address,
                        "name": device_in.name,
                        "reason": str(e),
                    }
                )

        return created_devices, failed_items

# 单例实例
device = CRUDDevice(Device)
