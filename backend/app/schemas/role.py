"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: role.py
@DateTime: 2025-12-30 14:00:00
@Docs: 角色 Role 相关 Schema 定义。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TimestampSchema


# 基础字段，仅包含可选或通用定义，避免在 Update 中覆写 Required 字段
class RoleBase(BaseModel):
    description: str | None = Field(None, description="描述")
    sort: int = Field(0, description="排序")


class RoleCreate(RoleBase):
    """
    创建角色 Schema
    """

    name: str = Field(..., description="角色名称")
    code: str = Field(..., description="角色编码")


class RoleUpdate(BaseModel):
    """
    更新角色 Schema
    不继承 RoleBase 或 RoleCreate，避免字段类型变异冲突。
    """

    name: str | None = Field(None, description="角色名称")
    code: str | None = Field(None, description="角色编码")
    description: str | None = Field(None, description="描述")
    sort: int | None = Field(None, description="排序")
    is_active: bool | None = Field(None, description="是否激活")


class RoleMenusUpdateRequest(BaseModel):
    """角色菜单/权限点绑定请求（全量覆盖，幂等）。"""

    menu_ids: list[UUID] = Field(default_factory=list, description="关联菜单ID列表")


class RoleResponse(RoleBase, TimestampSchema):
    """
    角色响应 Schema
    """

    id: UUID
    name: str  # 响应中必须存在
    code: str  # 响应中必须存在
    is_active: bool
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)
