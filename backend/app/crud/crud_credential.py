"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_credential.py
@DateTime: 2026-01-09 19:15:00
@Docs: 设备分组凭据 CRUD 操作。
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.credential import DeviceGroupCredential
from app.schemas.credential import DeviceGroupCredentialCreate, DeviceGroupCredentialUpdate

# 关联加载选项
_DEPT_OPTIONS = [selectinload(DeviceGroupCredential.dept)]


class CRUDCredential(CRUDBase[DeviceGroupCredential, DeviceGroupCredentialCreate, DeviceGroupCredentialUpdate]):
    """设备分组凭据 CRUD 操作类。"""

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        *,
        is_deleted: bool | None = False,
        options: Sequence[Any] | None = None,
    ) -> DeviceGroupCredential | None:
        """通过 ID 获取凭据（预加载部门关联）。"""
        return await super().get(db, id, is_deleted=is_deleted, options=options or _DEPT_OPTIONS)

    async def get_by_dept_and_group(
        self, db: AsyncSession, dept_id: UUID, device_group: str
    ) -> DeviceGroupCredential | None:
        """
        通过部门ID和设备分组获取凭据。

        Args:
            db: 数据库会话
            dept_id: 部门ID
            device_group: 设备分组

        Returns:
            DeviceGroupCredential | None: 凭据对象或 None
        """
        query = (
            select(self.model)
            .options(*_DEPT_OPTIONS)
            .where(self.model.dept_id == dept_id)
            .where(self.model.device_group == device_group)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def exists_credential(
        self,
        db: AsyncSession,
        dept_id: UUID,
        device_group: str,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        检查凭据是否已存在。

        Args:
            db: 数据库会话
            dept_id: 部门ID
            device_group: 设备分组
            exclude_id: 排除的凭据ID（用于更新时排除自身）

        Returns:
            bool: 凭据是否已存在
        """
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.dept_id == dept_id)
            .where(self.model.device_group == device_group)
            .where(self.model.is_deleted.is_(False))
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_by_dept(self, db: AsyncSession, dept_id: UUID) -> list[DeviceGroupCredential]:
        """
        获取指定部门的所有凭据。

        Args:
            db: 数据库会话
            dept_id: 部门ID

        Returns:
            list[DeviceGroupCredential]: 凭据列表
        """
        query = (
            select(self.model)
            .options(*_DEPT_OPTIONS)
            .where(self.model.dept_id == dept_id)
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.device_group)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

# 单例实例
credential = CRUDCredential(DeviceGroupCredential)
