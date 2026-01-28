"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_template_parameter.py
@DateTime: 2026-01-21 00:00:00
@Docs: TemplateParameter CRUD 操作（纯数据访问）。
"""

from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.template_parameter import TemplateParameter
from app.schemas.template import TemplateParameterCreate, TemplateParameterUpdate


class CRUDTemplateParameter(CRUDBase[TemplateParameter, TemplateParameterCreate, TemplateParameterUpdate]):
    """模板参数 CRUD 操作类（纯数据访问）。"""

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
            stmt = (
                update(self.model)
                .where(self.model.template_id == template_id)
                .where(self.model.is_deleted.is_(False))
                .values(is_deleted=True)
            )
        result = await db.execute(stmt)
        await db.flush()
        return getattr(result, "rowcount", 0) or 0


# 单例实例
template_parameter = CRUDTemplateParameter(TemplateParameter)
