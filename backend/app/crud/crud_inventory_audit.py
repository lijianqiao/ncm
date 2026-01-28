"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_inventory_audit.py
@DateTime: 2026-01-09 21:20:00
@Docs: 资产盘点任务 CRUD 操作。

提供资产盘点任务的数据库操作，包括分页查询、状态筛选等功能。
"""

from app.crud.base import CRUDBase
from app.models.inventory_audit import InventoryAudit
from app.schemas.inventory_audit import InventoryAuditCreate


class CRUDInventoryAudit(CRUDBase[InventoryAudit, InventoryAuditCreate, InventoryAuditCreate]):
    """资产盘点任务 CRUD 操作类。"""

    pass


inventory_audit_crud = CRUDInventoryAudit(InventoryAudit)
