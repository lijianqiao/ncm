"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_alert.py
@DateTime: 2026-01-10 03:20:00
@Docs: 告警 CRUD 操作。
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import AlertStatus
from app.crud.base import CRUDBase
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertUpdate


class CRUDAlert(CRUDBase[Alert, AlertCreate, AlertUpdate]):
    """告警 CRUD 操作类。"""

    async def get(self, db: AsyncSession, id: UUID) -> Alert | None:
        """通过 ID 获取告警（预加载关联设备/发现记录）。"""
        query = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(self.model.id == id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        alert_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        related_device_id: UUID | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[Alert], int]:
        """分页查询告警列表，支持筛选。"""
        page, page_size = self._validate_pagination(page, page_size)

        conditions: list[ColumnElement[bool]] = [self.model.is_deleted.is_(False)]

        if alert_type:
            conditions.append(self.model.alert_type == alert_type)
        if severity:
            conditions.append(self.model.severity == severity)
        if status:
            conditions.append(self.model.status == status)
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)

        keyword_clause = self._or_ilike_contains(keyword, [self.model.title, self.model.message])
        if keyword_clause is not None:
            conditions.append(keyword_clause)

        if start_time:
            conditions.append(self.model.created_at >= start_time)
        if end_time:
            conditions.append(self.model.created_at <= end_time)

        where_clause = and_(*conditions)
        count_stmt = select(func.count(Alert.id)).where(where_clause)
        stmt = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(where_clause)
            .order_by(self.model.created_at.desc())
        )
        return await self.paginate(db, stmt=stmt, count_stmt=count_stmt, page=page, page_size=page_size)

    async def exists_recent_open_alert(
        self,
        db: AsyncSession,
        *,
        alert_type: str,
        related_device_id: UUID | None = None,
        related_discovery_id: UUID | None = None,
        within_minutes: int = 24 * 60,
    ) -> bool:
        """去重：是否存在最近一段时间内的未关闭告警。"""
        since = datetime.now() - timedelta(minutes=within_minutes)
        conditions = [
            self.model.is_deleted.is_(False),
            self.model.alert_type == alert_type,
            self.model.created_at >= since,
            self.model.status != AlertStatus.CLOSED.value,
        ]
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)
        if related_discovery_id:
            conditions.append(self.model.related_discovery_id == related_discovery_id)

        query = select(func.count()).select_from(self.model).where(and_(*conditions))
        result = await db.execute(query)
        return (result.scalar() or 0) > 0

    async def get_latest_open_alert(
        self,
        db: AsyncSession,
        *,
        alert_type: str,
        related_device_id: UUID | None = None,
        related_discovery_id: UUID | None = None,
    ) -> Alert | None:
        """获取最新一条未关闭的告警（用于去重返回）。"""
        conditions = [
            self.model.is_deleted.is_(False),
            self.model.alert_type == alert_type,
            self.model.status != AlertStatus.CLOSED.value,
        ]
        if related_device_id:
            conditions.append(self.model.related_device_id == related_device_id)
        if related_discovery_id:
            conditions.append(self.model.related_discovery_id == related_discovery_id)

        query = (
            select(self.model)
            .options(selectinload(Alert.related_device), selectinload(Alert.related_discovery))
            .where(and_(*conditions))
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalars().first()

    # ===== 统计方法 =====

    async def get_stats(self, db: AsyncSession) -> dict:
        """
        获取告警统计数据（按类型/级别/状态分组）。

        Returns:
            dict: {
                "total": 总数,
                "by_type": {"config_change": n, ...},
                "by_severity": {"low": n, "medium": n, "high": n},
                "by_status": {"open": n, "ack": n, "closed": n}
            }
        """
        base_condition = self.model.is_deleted.is_(False)

        # 总数
        total_query = select(func.count(self.model.id)).where(base_condition)
        total_result = await db.execute(total_query)
        total = total_result.scalar() or 0

        # 按类型分组
        type_query = (
            select(self.model.alert_type, func.count(self.model.id))
            .where(base_condition)
            .group_by(self.model.alert_type)
        )
        type_result = await db.execute(type_query)
        by_type = {row[0]: row[1] for row in type_result.all()}

        # 按级别分组
        severity_query = (
            select(self.model.severity, func.count(self.model.id)).where(base_condition).group_by(self.model.severity)
        )
        severity_result = await db.execute(severity_query)
        by_severity = {row[0]: row[1] for row in severity_result.all()}

        # 按状态分组
        status_query = (
            select(self.model.status, func.count(self.model.id)).where(base_condition).group_by(self.model.status)
        )
        status_result = await db.execute(status_query)
        by_status = {row[0]: row[1] for row in status_result.all()}

        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
        }

    async def get_trend(self, db: AsyncSession, days: int = 7) -> list[dict]:
        """
        获取告警趋势数据（近 N 天每日新增）。

        Args:
            db: 数据库会话
            days: 天数，默认 7 天

        Returns:
            list[dict]: [{"date": "2026-01-20", "count": 5}, ...]
        """
        since = datetime.now() - timedelta(days=days)

        # 按日期分组统计
        query = (
            select(
                func.date(self.model.created_at).label("date"),
                func.count(self.model.id).label("count"),
            )
            .where(self.model.is_deleted.is_(False))
            .where(self.model.created_at >= since)
            .group_by(func.date(self.model.created_at))
            .order_by(func.date(self.model.created_at))
        )
        result = await db.execute(query)
        rows = result.all()

        return [{"date": str(row.date), "count": row.count} for row in rows]


alert_crud = CRUDAlert(Alert)
