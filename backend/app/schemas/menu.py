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
    type: MenuType = Field(MenuType.MENU, description="菜单类型（目录/菜单/权限点）")
    parent_id: UUID | None = Field(None, description="父菜单ID")
    path: str | None = Field(None, description="路由路径")
    component: str | None = Field(None, description="组件路径")
    icon: str | None = Field(None, description="图标")
    sort: int = Field(0, description="排序")
    is_hidden: bool = Field(False, description="是否隐藏")
    permission: str | None = Field(None, description="权限标识")


class MenuCreate(MenuBase):
    """
    创建菜单 Schema
    """

    title: str = Field(..., description="菜单标题")
    name: str = Field(..., description="组件名称")


class MenuUpdate(BaseModel):
    """
    更新菜单 Schema
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
    """
    菜单响应 Schema
    """

    id: UUID
    title: str
    name: str
    is_deleted: bool = False
    is_active: bool = True
    children: list["MenuResponse"] | None = None

    model_config = ConfigDict(from_attributes=True)
