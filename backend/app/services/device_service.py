"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: device_service.py
@DateTime: 2026-01-09 19:20:00
@Docs: 设备服务业务逻辑 (Device Service Logic).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.encryption import encrypt_password
from app.core.enums import AuthType
from app.core.exceptions import BadRequestException, NotFoundException
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

    async def get_devices_paginated(
        self, query: DeviceListQuery
    ) -> tuple[list[Device], int]:
        """
        获取分页过滤的设备列表。

        Args:
            query: 查询参数

        Returns:
            (items, total): 设备列表和总数
        """
        return await self.device_crud.get_multi_paginated_filtered(
            self.db,
            page=query.page,
            page_size=query.page_size,
            keyword=query.keyword,
            vendor=query.vendor.value if query.vendor else None,
            status=query.status.value if query.status else None,
            device_group=query.device_group.value if query.device_group else None,
            dept_id=query.dept_id,
        )

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
        创建设备。

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
        更新设备。

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
        删除设备（软删除）。

        Args:
            device_id: 设备ID

        Returns:
            Device: 删除的设备

        Raises:
            NotFoundException: 设备不存在
        """
        device = await self.device_crud.remove(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")
        return device

    @transactional()
    async def batch_delete_devices(self, ids: list[UUID]) -> DeviceBatchResult:
        """
        批量删除设备（软删除）。

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
        批量创建设备。

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

        created_devices, failed_items = await self.device_crud.batch_create(
            self.db, devices_in=obj_in.devices
        )

        # 处理成功创建的设备的密码加密
        for i, device in enumerate(created_devices):
            device_create = obj_in.devices[i] if i < len(obj_in.devices) else None
            if (
                device_create
                and device_create.auth_type == AuthType.STATIC
                and device_create.password
            ):
                device.password_encrypted = encrypt_password(device_create.password)
                self.db.add(device)

        await self.db.flush()

        return DeviceBatchResult(
            success_count=len(created_devices),
            failed_count=len(failed_items),
            failed_items=failed_items,
        )

    async def get_recycle_bin(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Device], int]:
        """
        获取回收站中的设备。

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            (items, total): 设备列表和总数
        """
        return await self.device_crud.get_recycle_bin(self.db, page=page, page_size=page_size)

    @transactional()
    async def restore_device(self, device_id: UUID) -> Device:
        """
        恢复设备（从回收站）。

        Args:
            device_id: 设备ID

        Returns:
            Device: 恢复的设备

        Raises:
            NotFoundException: 设备不存在
            BadRequestException: 设备未被删除或 IP 地址冲突
        """
        device = await self.device_crud.restore(self.db, id=device_id)
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
