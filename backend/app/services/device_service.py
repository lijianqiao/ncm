"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: device_service.py
@DateTime: 2026-01-09 19:20:00
@Docs: 设备服务业务逻辑 (Device Service Logic).
"""

import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache as cache_module
from app.core.decorator import transactional
from app.core.encryption import encrypt_password
from app.core.enums import AuthType, DeviceStatus
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.lifecycle import validate_transition
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.models.device import Device
from app.schemas.device import (
    DeviceBatchCreate,
    DeviceBatchResult,
    DeviceCreate,
    DeviceListQuery,
    DeviceUpdate,
)


class DeviceService:
    """
    设备服务类。
    通过构造函数注入 CRUD 实例，实现解耦。
    """

    def __init__(self, db: AsyncSession, device_crud: CRUDDevice, credential_crud: CRUDCredential):
        self.db = db
        self.device_crud = device_crud
        self.credential_crud = credential_crud
        self._post_commit_tasks: list = []

    async def get_devices_paginated(self, query: DeviceListQuery) -> tuple[list[Device], int]:
        """
        获取分页过滤的设备列表。

        Args:
            query: 查询参数

        Returns:
            (items, total): 设备列表和总数
        """
        return await self.device_crud.get_paginated(
            self.db,
            page=query.page,
            page_size=query.page_size,
            max_size=10000,
            keyword=query.keyword,
            keyword_columns=[Device.name, Device.ip_address],
            order_by=Device.created_at.desc(),
            options=self.device_crud._DEVICE_OPTIONS,
            vendor=query.vendor.value if query.vendor else None,
            status=query.status.value if query.status else None,
            device_group=query.device_group.value if query.device_group else None,
            dept_id=query.dept_id,
        )

    async def get_status_counts(self) -> dict[str, int]:
        """
        获取各状态的设备数量。

        Returns:
            dict: 各状态对应的设备数量（stock/running/maintenance/retired/total）
        """
        stmt = (
            select(Device.status, func.count(Device.id))
            .where(Device.is_deleted == False)  # noqa: E712
            .group_by(Device.status)
        )
        rows = (await self.db.execute(stmt)).all()
        counts = {str(status): count for status, count in rows}

        # 映射枚举值到前端字段
        # IN_STOCK -> stock, ACTIVE/IN_USE -> running, MAINTENANCE -> maintenance, RETIRED -> retired
        return {
            "stock": counts.get(DeviceStatus.IN_STOCK.value, 0),
            "running": counts.get(DeviceStatus.ACTIVE.value, 0) + counts.get(DeviceStatus.IN_USE.value, 0),
            "maintenance": counts.get(DeviceStatus.MAINTENANCE.value, 0),
            "retired": counts.get(DeviceStatus.RETIRED.value, 0),
            "total": sum(counts.values()),
        }

    async def get_device(self, device_id: UUID) -> Device:
        """
        根据 ID 获取设备。

        Args:
            device_id: 设备ID

        Returns:
            Device: 设备对象

        Raises:
            NotFoundException: 设备不存在
        """
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")
        return device

    @transactional()
    async def create_device(self, obj_in: DeviceCreate) -> Device:
        """
        创建设备

        Args:
            obj_in: 设备创建数据

        Returns:
            Device: 创建的设备

        Raises:
            BadRequestException: IP 地址已存在或业务校验失败
        """
        # 1. 检查 IP 地址唯一性
        if await self.device_crud.exists_ip(self.db, obj_in.ip_address):
            raise BadRequestException(message=f"IP 地址 {obj_in.ip_address} 已存在")

        # 2. 静态认证类型校验
        if obj_in.auth_type == AuthType.STATIC:
            if not obj_in.username or not obj_in.password:
                raise BadRequestException(message="静态认证类型必须提供用户名和密码")

        # 3. OTP 认证类型校验
        if obj_in.auth_type in (AuthType.OTP_SEED, AuthType.OTP_MANUAL):
            if not obj_in.dept_id:
                raise BadRequestException(message="OTP 认证类型必须关联部门")
            # 检查对应的凭据是否存在
            credential = await self.credential_crud.get_by_dept_and_group(
                self.db, obj_in.dept_id, obj_in.device_group.value
            )
            if not credential:
                raise BadRequestException(
                    message=f"部门 {obj_in.dept_id} 的设备分组 {obj_in.device_group.value} 没有配置凭据"
                )

        # 4. 准备创建数据
        create_data = obj_in.model_dump(exclude={"password"}, exclude_unset=True)

        # 5. 处理静态密码加密
        if obj_in.auth_type == AuthType.STATIC and obj_in.password:
            create_data["password_encrypted"] = encrypt_password(obj_in.password)

        # 6. 创建设备
        db_obj = Device(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    @transactional()
    async def update_device(self, device_id: UUID, obj_in: DeviceUpdate) -> Device:
        """
        更新设备

        Args:
            device_id: 设备ID
            obj_in: 设备更新数据

        Returns:
            Device: 更新后的设备

        Raises:
            NotFoundException: 设备不存在
            BadRequestException: IP 地址已存在或业务校验失败
        """
        # 1. 获取设备
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        # 2. 检查 IP 地址唯一性（如果更新了 IP）
        if obj_in.ip_address and obj_in.ip_address != device.ip_address:
            if await self.device_crud.exists_ip(self.db, obj_in.ip_address, exclude_id=device_id):
                raise BadRequestException(message=f"IP 地址 {obj_in.ip_address} 已存在")

        # 3. 处理更新数据
        update_data = obj_in.model_dump(exclude={"password"}, exclude_unset=True)

        # 4. 处理静态密码加密（如果提供了新密码）
        if obj_in.password:
            auth_type = obj_in.auth_type or AuthType(device.auth_type)
            if auth_type == AuthType.STATIC:
                update_data["password_encrypted"] = encrypt_password(obj_in.password)

        # 5. 更新设备
        return await self.device_crud.update(self.db, db_obj=device, obj_in=update_data)

    @transactional()
    async def delete_device(self, device_id: UUID) -> Device:
        """
        删除设备（软删除）

        Args:
            device_id: 设备ID

        Returns:
            Device: 删除的设备

        Raises:
            NotFoundException: 设备不存在
        """
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")
        success_count, _ = await self.device_crud.batch_remove(self.db, ids=[device_id])
        if success_count == 0:
            raise NotFoundException(message="设备不存在")
        # 刷新对象以获取最新状态（包括 is_deleted=True）
        await self.db.refresh(device)
        return device

    @transactional()
    async def batch_delete_devices(self, ids: list[UUID]) -> DeviceBatchResult:
        """
        批量删除设备（软删除）

        Args:
            ids: 设备ID列表

        Returns:
            DeviceBatchResult: 批量操作结果
        """
        success_count, failed_ids = await self.device_crud.batch_remove(self.db, ids=ids)
        return DeviceBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_items=[{"id": str(id_), "reason": "设备不存在或删除失败"} for id_ in failed_ids],
        )

    @transactional()
    async def batch_create_devices(self, obj_in: DeviceBatchCreate) -> DeviceBatchResult:
        """
        批量创建设备

        Args:
            obj_in: 批量创建数据

        Returns:
            DeviceBatchResult: 批量操作结果
        """
        # 预处理：为静态认证类型加密密码
        for device_create in obj_in.devices:
            if device_create.auth_type == AuthType.STATIC and device_create.password:
                # 密码会在 CRUD 层排除，这里标记处理
                pass

        created_devices, failed_items = await self.device_crud.batch_create(self.db, devices_in=obj_in.devices)

        # 处理成功创建的设备的密码加密
        for i, device in enumerate(created_devices):
            device_create = obj_in.devices[i] if i < len(obj_in.devices) else None
            if device_create and device_create.auth_type == AuthType.STATIC and device_create.password:
                device.password_encrypted = encrypt_password(device_create.password)
                self.db.add(device)

        await self.db.flush()

        return DeviceBatchResult(
            success_count=len(created_devices),
            failed_count=len(failed_items),
            failed_items=failed_items,
        )

    async def get_recycle_bin(self, page: int = 1, page_size: int = 20) -> tuple[list[Device], int]:
        """获取回收站中的设备列表。"""
        return await self.device_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            max_size=10000,
            order_by=Device.updated_at.desc(),
            is_deleted=True,
        )

    @transactional()
    async def transition_status(
        self,
        device_id: UUID,
        *,
        to_status: DeviceStatus,
        reason: str | None = None,
        operator_id: UUID | None = None,
    ) -> Device:
        """设备状态流转（生命周期状态机）。"""
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        from_status = str(device.status)
        to_value = to_status.value
        validate_transition(from_status, to_value)

        device.status = to_value

        # 补充关键时间字段（最小化变更）
        if to_status == DeviceStatus.RETIRED:
            from datetime import UTC, datetime

            device.retired_at = datetime.now(UTC)

        self.db.add(device)
        await self.db.flush()
        await self.db.refresh(device)

        # 缓存失效（统计缓存）
        await self._invalidate_lifecycle_cache()
        return device

    @transactional()
    async def batch_transition_status(
        self,
        ids: list[UUID],
        *,
        to_status: DeviceStatus,
        reason: str | None = None,
        operator_id: UUID | None = None,
    ) -> tuple[int, list[dict]]:
        """批量状态流转。返回 (success_count, failed_items)。"""
        success = 0
        failed: list[dict] = []

        for device_id in ids:
            try:
                await self.transition_status(device_id, to_status=to_status, reason=reason, operator_id=operator_id)
                success += 1
            except Exception as e:
                failed.append({"id": str(device_id), "reason": str(e)})

        return success, failed

    async def _invalidate_lifecycle_cache(self) -> None:
        if cache_module.redis_client is None:
            return
        try:
            # 简化：删除所有 stats key（规模小可接受）
            # key 规范：v1:ncm:device:lifecycle:stats:{hash}
            keys = await cache_module.redis_client.keys("v1:ncm:device:lifecycle:stats:*")
            if keys:
                await cache_module.redis_client.delete(*keys)
        except Exception:
            return

    async def get_lifecycle_stats(
        self,
        *,
        dept_id: UUID | None = None,
        vendor: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """生命周期统计（按状态/厂商/部门）。支持 60 秒缓存。"""
        cache_key = None
        if cache_module.redis_client is not None:
            key_obj = {"dept_id": str(dept_id) if dept_id else None, "vendor": vendor}
            cache_hash = hashlib.md5(json.dumps(key_obj, sort_keys=True).encode("utf-8")).hexdigest()
            cache_key = f"v1:ncm:device:lifecycle:stats:{cache_hash}"
            try:
                cached = await cache_module.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                cache_key = None

        base = select(Device)
        if dept_id:
            base = base.where(Device.dept_id == dept_id)
        if vendor:
            base = base.where(Device.vendor == vendor)

        # 按状态统计
        status_stmt = select(Device.status, func.count(Device.id)).select_from(Device)
        if dept_id:
            status_stmt = status_stmt.where(Device.dept_id == dept_id)
        if vendor:
            status_stmt = status_stmt.where(Device.vendor == vendor)
        status_stmt = status_stmt.group_by(Device.status)

        vendor_stmt = select(Device.vendor, func.count(Device.id)).select_from(Device)
        if dept_id:
            vendor_stmt = vendor_stmt.where(Device.dept_id == dept_id)
        vendor_stmt = vendor_stmt.group_by(Device.vendor)

        dept_stmt = select(Device.dept_id, func.count(Device.id)).select_from(Device)
        if vendor:
            dept_stmt = dept_stmt.where(Device.vendor == vendor)
        dept_stmt = dept_stmt.group_by(Device.dept_id)

        status_rows = (await self.db.execute(status_stmt)).all()
        vendor_rows = (await self.db.execute(vendor_stmt)).all()
        dept_rows = (await self.db.execute(dept_stmt)).all()

        data = {
            "by_status": {str(k): int(v) for k, v in status_rows},
            "by_vendor": {str(k): int(v) for k, v in vendor_rows},
            "by_dept": {str(k) if k else "null": int(v) for k, v in dept_rows},
        }

        if cache_module.redis_client is not None and cache_key:
            try:
                await cache_module.redis_client.setex(cache_key, 60, json.dumps(data, ensure_ascii=False))
            except Exception:
                pass
        return data

    @transactional()
    async def restore_device(self, device_id: UUID) -> Device:
        """
        恢复设备（从回收站）

        Args:
            device_id: 设备ID

        Returns:
            Device: 恢复的设备

        Raises:
            NotFoundException: 设备不存在
            BadRequestException: 设备未被删除或IP 地址冲突
        """
        success_count, _ = await self.device_crud.batch_restore(self.db, ids=[device_id])
        if success_count == 0:
            raise NotFoundException(message="设备不存在")

        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        # 检查恢复后 IP 地址是否冲突
        if await self.device_crud.exists_ip(self.db, device.ip_address, exclude_id=device_id):
            # 回滚恢复
            device.is_deleted = True
            self.db.add(device)
            await self.db.flush()
            raise BadRequestException(message=f"IP 地址 {device.ip_address} 已被其他设备使用")

        return device

    @transactional()
    async def batch_restore_devices(self, ids: list[UUID]) -> DeviceBatchResult:
        """
        批量恢复设备（从回收站）

        Args:
            ids: 设备ID列表

        Returns:
            DeviceBatchResult: 批量操作结果
        """
        success_count, failed_ids = await self.device_crud.batch_restore(self.db, ids=ids)
        return DeviceBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_items=[{"id": str(id_), "reason": "设备不存在或恢复失败"} for id_ in failed_ids],
        )

    @transactional()
    async def hard_delete_device(self, device_id: UUID) -> None:
        """
        彻底删除设备（硬删除）

        Args:
            device_id: 设备ID

        Raises:
            NotFoundException: 设备不存在或未被软删除
        """
        stmt = select(Device).where(Device.id == device_id).where(Device.is_deleted.is_(True))
        deleted_device = (await self.db.execute(stmt)).scalars().first()
        if not deleted_device:
            raise NotFoundException(message="设备不存在或未被软删除")

        success_count, _ = await self.device_crud.batch_remove(self.db, ids=[device_id], hard_delete=True)
        if success_count == 0:
            raise NotFoundException(message="彻底删除失败")

    @transactional()
    async def batch_hard_delete_devices(self, ids: list[UUID]) -> DeviceBatchResult:
        """
        批量彻底删除设备（硬删除）

        Args:
            ids: 设备ID列表

        Returns:
            DeviceBatchResult: 批量操作结果
        """
        success_count, failed_ids = await self.device_crud.batch_remove(self.db, ids=ids, hard_delete=True)
        return DeviceBatchResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_items=[{"id": str(id_), "reason": "设备不存在或彻底删除失败"} for id_ in failed_ids],
        )
