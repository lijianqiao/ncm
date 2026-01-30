"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: menu.py
@DateTime: 2025-12-30 14:05:00
@Docs: 菜单 Menu 相关 Schema 定义。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import MenuType
from app.schemas.common import TimestampSchema


class MenuBase(BaseModel):
    """菜单基础 Schema。

    菜单的基础字段定义，用于创建和更新菜单。

    Attributes:
        type (MenuType): 菜单类型（目录/菜单/权限点），默认 MENU。
        parent_id (UUID | None): 父菜单 ID。
        path (str | None): 路由路径。
        component (str | None): 组件路径。
        icon (str | None): 图标。
        sort (int): 排序，默认 0。
        is_hidden (bool): 是否隐藏，默认 False。
        permission (str | None): 权限标识。
    """

    type: MenuType = Field(MenuType.MENU, description="菜单类型（目录/菜单/权限点）")
    parent_id: UUID | None = Field(None, description="父菜单ID")
    path: str | None = Field(None, description="路由路径")
    component: str | None = Field(None, description="组件路径")
    icon: str | None = Field(None, description="图标")
    sort: int = Field(0, description="排序")
    is_hidden: bool = Field(False, description="是否隐藏")
    permission: str | None = Field(None, description="权限标识")


class MenuCreate(MenuBase):
    """创建菜单请求 Schema。

    用于创建新菜单的请求体。

    Attributes:
        title (str): 菜单标题。
        name (str): 组件名称。
    """

    title: str = Field(..., description="菜单标题")
    name: str = Field(..., description="组件名称")


class MenuUpdate(BaseModel):
    """更新菜单请求 Schema。

    用于更新菜单信息的请求体，所有字段可选。

    Attributes:
        title (str | None): 菜单标题。
        name (str | None): 组件名称。
        type (MenuType | None): 菜单类型。
        parent_id (UUID | None): 父菜单 ID。
        path (str | None): 路由路径。
        component (str | None): 组件路径。
        icon (str | None): 图标。
        sort (int | None): 排序。
        is_hidden (bool | None): 是否隐藏。
        is_active (bool | None): 是否激活。
        permission (str | None): 权限标识。
    """

    title: str | None = None
    name: str | None = None
    type: MenuType | None = None
    parent_id: UUID | None = None
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    sort: int | None = None
    is_hidden: bool | None = None
    is_active: bool | None = None
    permission: str | None = None


class MenuResponse(MenuBase, TimestampSchema):
    """菜单响应 Schema。

    用于返回菜单信息的响应体，包含菜单基本信息和子菜单列表。

    Attributes:
        id (UUID): 菜单 ID。
        title (str): 菜单标题。
        name (str): 组件名称。
        is_deleted (bool): 是否删除，默认 False。
        is_active (bool): 是否激活，默认 True。
        children (list[MenuResponse] | None): 子菜单列表。
    """

    id: UUID
    title: str
    name: str
    is_deleted: bool = False
    is_active: bool = True
    children: list["MenuResponse"] | None = None

    model_config = ConfigDict(from_attributes=True)
