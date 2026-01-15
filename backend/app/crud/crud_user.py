"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: crud_user.py
@DateTime: 2025-12-30 12:15:00
@Docs: User CRUD operations.
"""

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.data_scope import apply_dept_filter
from app.core.security import get_password_hash
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    @staticmethod
    def _apply_keyword_filter(stmt, *, keyword: str | None):
        kw = CRUDBase._normalize_keyword(keyword)
        if not kw:
            return stmt

        clauses = []

        text_clause = CRUDBase._or_ilike_contains(
            kw,
            [
                User.username,
                User.nickname,
                User.email,
                User.phone,
                User.gender,
            ],
        )
        if text_clause is not None:
            clauses.append(text_clause)

        # 状态（启用/禁用）
        active_true = {"启用", "正常", "有效", "active", "enabled", "true", "是", "1"}
        active_false = {"禁用", "停用", "无效", "inactive", "disabled", "false", "否", "0"}
        active_clause = CRUDBase._bool_clause_from_keyword(
            kw, User.is_active, true_values=active_true, false_values=active_false
        )
        if active_clause is not None:
            clauses.append(active_clause)

        # 超级管理员
        su_true = {"超级管理员", "超管", "superuser"}
        su_false = {"普通用户", "非超管"}
        su_clause = CRUDBase._bool_clause_from_keyword(
            kw, User.is_superuser, true_values=su_true, false_values=su_false
        )
        if su_clause is not None:
            clauses.append(su_clause)

        return stmt.where(or_(*clauses))

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_superuser: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        page, page_size = self._validate_pagination(page, page_size)

        count_stmt = select(func.count(User.id)).where(User.is_deleted.is_(False))
        if is_superuser is not None:
            count_stmt = count_stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active.is_(is_active))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(User).options(selectinload(User.dept)).where(User.is_deleted.is_(False))
        if is_superuser is not None:
            stmt = stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_multi_paginated_with_scope(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_superuser: bool | None = None,
        is_active: bool | None = None,
        dept_ids: list | None = None,
        current_user_id: UUID | None = None,
    ) -> tuple[list[User], int]:
        """
        带数据权限过滤的分页查询。

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 关键词
            is_superuser: 是否超级管理员过滤
            is_active: 是否启用过滤
            dept_ids: 可访问的部门 ID 列表（None 表示不过滤）
            current_user_id: 当前用户 ID（用于 SELF 模式）

        Returns:
            用户列表和总数
        """
        page, page_size = self._validate_pagination(page, page_size)

        # 构建基础查询
        count_stmt = select(func.count(User.id)).where(User.is_deleted.is_(False))
        if is_superuser is not None:
            count_stmt = count_stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active.is_(is_active))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)

        # 应用数据权限过滤
        count_stmt = apply_dept_filter(
            count_stmt,
            dept_ids=dept_ids,
            user_id=current_user_id,
            dept_column=User.dept_id,
            created_by_column=User.id,  # 用户表特殊：“仅本人”指能看到自己
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(User).options(selectinload(User.dept)).where(User.is_deleted.is_(False))
        if is_superuser is not None:
            stmt = stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)

        # 应用数据权限过滤
        stmt = apply_dept_filter(
            stmt,
            dept_ids=dept_ids,
            user_id=current_user_id,
            dept_column=User.dept_id,
            created_by_column=User.id,
        )
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_username(self, db: AsyncSession, *, username: str) -> User | None:
        """
        根据用户名查询用户 (排除已软删除)。
        """
        result = await db.execute(select(User).where(User.username == username, User.is_deleted.is_(False)))
        return result.scalars().first()

    async def get_by_unique_field(
        self,
        db: AsyncSession,
        *,
        field: Literal["username", "email", "phone"],
        value: str,
        include_deleted: bool = False,
    ) -> User | None:
        col_map = {
            "username": User.username,
            "email": User.email,
            "phone": User.phone,
        }
        col = col_map[field]
        stmt = select(User).where(col == value)
        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_username_include_deleted(self, db: AsyncSession, *, username: str) -> User | None:
        """
        根据用户名查询用户 (包含已软删除)。
        """
        return await self.get_by_unique_field(db, field="username", value=username, include_deleted=True)

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        """
        根据邮箱查询用户 (排除已软删除)。
        """
        result = await db.execute(select(User).where(User.email == email, User.is_deleted.is_(False)))
        return result.scalars().first()

    async def get_by_email_include_deleted(self, db: AsyncSession, *, email: str) -> User | None:
        """
        根据邮箱查询用户 (包含已软删除)。
        """
        return await self.get_by_unique_field(db, field="email", value=email, include_deleted=True)

    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> User | None:
        """
        根据手机号查询用户 (排除已软删除)。
        """
        result = await db.execute(select(User).where(User.phone == phone, User.is_deleted.is_(False)))
        return result.scalars().first()

    async def get_by_phone_include_deleted(self, db: AsyncSession, *, phone: str) -> User | None:
        """
        根据手机号查询用户 (包含已软删除)。
        """
        return await self.get_by_unique_field(db, field="phone", value=phone, include_deleted=True)

    async def get_with_roles(self, db: AsyncSession, *, id: UUID) -> User | None:
        """获取用户并预加载 roles，避免后续访问触发惰性加载。"""

        result = await db.execute(
            select(User).options(selectinload(User.roles)).where(User.id == id, User.is_deleted.is_(False))
        )
        return result.scalars().first()

    async def count_active(self, db: AsyncSession) -> int:
        """
        统计活跃用户数。
        """
        result = await db.execute(
            select(func.count(User.id)).where(User.is_active.is_(True), User.is_deleted.is_(False))
        )
        return result.scalar_one()

    async def get_multi_deleted_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_superuser: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """
        获取已删除用户列表 (分页)。
        """
        page, page_size = self._validate_pagination(page, page_size)

        count_stmt = select(func.count(User.id)).where(User.is_deleted.is_(True))
        if is_superuser is not None:
            count_stmt = count_stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active.is_(is_active))
        count_stmt = self._apply_keyword_filter(count_stmt, keyword=keyword)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = select(User).options(selectinload(User.dept)).where(User.is_deleted.is_(True))
        if is_superuser is not None:
            stmt = stmt.where(User.is_superuser.is_(is_superuser))
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        stmt = self._apply_keyword_filter(stmt, keyword=keyword)
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            phone=obj_in.phone,
            nickname=obj_in.nickname,
            gender=obj_in.gender,
            is_active=obj_in.is_active,
            is_superuser=obj_in.is_superuser,
            dept_id=obj_in.dept_id,
            password=get_password_hash(obj_in.password),
        )
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate | dict[str, Any]) -> User:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            update_data["password"] = hashed_password

        return await super().update(db, db_obj=db_obj, obj_in=update_data)


user = CRUDUser(User)
