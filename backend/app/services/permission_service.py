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
    """权限字典服务。"""

    async def list_permissions(self) -> list[PermissionDictItem]:
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
