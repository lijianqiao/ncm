"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: permission_service.py
@DateTime: 2026-01-06 00:00:00
@Docs: 权限字典服务（权限码以代码为源）。
"""

from app.core.permissions import list_permission_defs
from app.schemas.permission import PermissionDictItem


class PermissionService:
    """
    权限字典服务类。

    权限码以代码为源，提供权限字典查询功能。
    """

    async def list_permissions(self) -> list[PermissionDictItem]:
        """
        获取所有权限字典项。

        Returns:
            list[PermissionDictItem]: 权限字典项列表
        """
        items: list[PermissionDictItem] = []
        for d in list_permission_defs():
            items.append(
                PermissionDictItem(
                    code=d.code.value,
                    name=d.name,
                    description=d.description,
                )
            )
        return items
