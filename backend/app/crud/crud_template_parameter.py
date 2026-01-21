"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template_parameter.py
@DateTime: 2026-01-21 00:00:00
@Docs: TemplateParameter CRUD 操作。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.template_parameter import TemplateParameter
from app.schemas.template import TemplateParameterCreate, TemplateParameterUpdate


class CRUDTemplateParameter(CRUDBase[TemplateParameter, TemplateParameterCreate, TemplateParameterUpdate]):
    """模板参数 CRUD 操作类。"""

    async def get_by_template(
        self,
        db: AsyncSession,
        template_id: UUID,
    ) -> list[TemplateParameter]:
        """
        获取指定模板的所有参数（按 order 排序）。

        Args:
            db: 数据库会话
            template_id: 模板 ID

        Returns:
            参数列表
        """
        stmt = (
            select(self.model)
            .where(self.model.template_id == template_id)
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.order)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_for_template(
        self,
        db: AsyncSession,
        *,
        template_id: UUID,
        params: list[TemplateParameterCreate],
    ) -> list[TemplateParameter]:
        """
        为模板批量创建参数。

        Args:
            db: 数据库会话
            template_id: 模板 ID
            params: 参数创建列表

        Returns:
            创建的参数列表
        """
        created = []
        for idx, param in enumerate(params):
            obj = TemplateParameter(
                template_id=template_id,
                name=param.name,
                label=param.label,
                param_type=param.param_type.value,
                required=param.required,
                default_value=param.default_value,
                description=param.description,
                options=param.options,
                min_value=param.min_value,
                max_value=param.max_value,
                pattern=param.pattern,
                order=param.order if param.order > 0 else idx,
            )
            db.add(obj)
            created.append(obj)

        await db.flush()
        for obj in created:
            await db.refresh(obj)
        return created

    async def delete_by_template(
        self,
        db: AsyncSession,
        template_id: UUID,
        *,
        hard_delete: bool = False,
    ) -> int:
        """
        删除指定模板的所有参数。

        Args:
            db: 数据库会话
            template_id: 模板 ID
            hard_delete: 是否硬删除

        Returns:
            删除的记录数
        """
        if hard_delete:
            stmt = delete(self.model).where(self.model.template_id == template_id)
        else:
            # 软删除：只标记未删除的记录
            from sqlalchemy import update

            stmt = (
                update(self.model)
                .where(self.model.template_id == template_id)
                .where(self.model.is_deleted.is_(False))
                .values(is_deleted=True)
            )
        result = await db.execute(stmt)
        await db.flush()
        # CursorResult 有 rowcount 属性，使用 getattr 避免类型检查器报错
        return getattr(result, "rowcount", 0) or 0

    async def sync_parameters(
        self,
        db: AsyncSession,
        *,
        template_id: UUID,
        params: list[TemplateParameterCreate],
    ) -> list[TemplateParameter]:
        """
        同步模板参数（先删除旧参数，再创建新参数）。

        Args:
            db: 数据库会话
            template_id: 模板 ID
            params: 新参数列表

        Returns:
            创建的参数列表
        """
        # 硬删除旧参数
        await self.delete_by_template(db, template_id, hard_delete=True)

        # 创建新参数
        if params:
            return await self.create_for_template(db, template_id=template_id, params=params)
        return []


# 单例实例
template_parameter = CRUDTemplateParameter(TemplateParameter)
