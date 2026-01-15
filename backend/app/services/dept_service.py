"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: dept_service.py
@DateTime: 2026-01-08 14:12:00
@Docs: 部门服务业务逻辑 (Department Service Logic)。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.decorator import transactional
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_dept import CRUDDept
from app.models.dept import Department
from app.schemas.dept import DeptCreate, DeptResponse, DeptUpdate


class DeptService:
    """部门服务类。"""

    def __init__(self, db: AsyncSession, dept_crud: CRUDDept):
        self.db = db
        self.dept_crud = dept_crud

    @staticmethod
    def _to_dept_response(dept: Department, *, children: list[DeptResponse] | None = None) -> DeptResponse:
        """将 ORM Department 转为响应对象。"""
        return DeptResponse(
            id=dept.id,
            name=dept.name,
            code=dept.code,
            parent_id=dept.parent_id,
            sort=dept.sort,
            leader=dept.leader,
            phone=dept.phone,
            email=dept.email,
            is_active=dept.is_active,
            is_deleted=dept.is_deleted,
            created_at=dept.created_at,
            updated_at=dept.updated_at,
            children=children or [],
        )

    def _build_tree_response(
        self,
        dept: Department,
        *,
        children_map: dict[UUID | None, list[Department]],
        visited: set[UUID],
    ) -> DeptResponse:
        """递归构建部门树响应。

        注意：异步 SQLAlchemy 下禁止在这里触发 relationship 懒加载，否则会出现 MissingGreenlet。
        因此 children 通过 children_map 提供，不直接访问 dept.children。
        """

        if dept.id in visited:
            return self._to_dept_response(dept, children=[])
        visited.add(dept.id)

        children = children_map.get(dept.id, [])
        children.sort(key=lambda x: x.sort)

        children_responses: list[DeptResponse] = []
        for child in children:
            if not child.is_deleted:
                children_responses.append(self._build_tree_response(child, children_map=children_map, visited=visited))

        return self._to_dept_response(dept, children=children_responses)

    async def get_dept_tree(self, *, keyword: str | None = None, is_active: bool | None = None) -> list[DeptResponse]:
        """
        获取部门树结构。

        Args:
            is_active: 是否启用过滤

        Returns:
            部门树列表
        """
        depts = await self.dept_crud.get_tree(self.db, keyword=keyword, is_active=is_active)

        by_id: dict[UUID, Department] = {d.id: d for d in depts}
        children_map: dict[UUID | None, list[Department]] = {}
        for d in depts:
            children_map.setdefault(d.parent_id, []).append(d)

        roots: list[Department] = []
        for d in depts:
            if d.parent_id is None or d.parent_id not in by_id:
                roots.append(d)
        roots.sort(key=lambda x: x.sort)

        visited: set[UUID] = set()
        return [self._build_tree_response(r, children_map=children_map, visited=visited) for r in roots]

    async def get_depts_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[DeptResponse], int]:
        """
        获取分页部门列表。

        Args:
            page: 页码
            page_size: 每页数量
            keyword: 关键词
            is_active: 是否启用过滤

        Returns:
            部门列表和总数
        """
        depts, total = await self.dept_crud.get_multi_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
        )
        return [self._to_dept_response(d, children=[]) for d in depts], total

    async def get_deleted_depts(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[DeptResponse], int]:
        """获取已删除部门列表（回收站）。"""
        depts, total = await self.dept_crud.get_multi_deleted_paginated(
            self.db,
            page=page,
            page_size=page_size,
            keyword=keyword,
            is_active=is_active,
        )
        return [self._to_dept_response(d, children=[]) for d in depts], total

    async def get_dept(self, *, dept_id: UUID) -> DeptResponse:
        """
        获取单个部门。

        Args:
            dept_id: 部门 ID

        Returns:
            部门对象

        Raises:
            NotFoundException: 部门不存在时
        """
        dept = await self.dept_crud.get(self.db, id=dept_id)
        if not dept:
            raise NotFoundException(message="部门不存在")
        return self._to_dept_response(dept, children=[])

    @transactional()
    async def create_dept(self, *, obj_in: DeptCreate) -> DeptResponse:
        """
        创建部门。

        Args:
            obj_in: 部门创建数据

        Returns:
            创建的部门对象

        Raises:
            BadRequestException: 编码已存在时
        """
        # 检查编码是否已存在
        if await self.dept_crud.exists_code(self.db, code=obj_in.code):
            raise BadRequestException(message=f"部门编码 '{obj_in.code}' 已存在")

        # 检查父部门是否存在
        if obj_in.parent_id:
            parent = await self.dept_crud.get(self.db, id=obj_in.parent_id)
            if not parent:
                raise NotFoundException(message="父部门不存在")

        dept = await self.dept_crud.create(self.db, obj_in=obj_in)
        return self._to_dept_response(dept, children=[])

    @transactional()
    async def update_dept(self, *, dept_id: UUID, obj_in: DeptUpdate) -> DeptResponse:
        """
        更新部门。

        Args:
            dept_id: 部门 ID
            obj_in: 部门更新数据

        Returns:
            更新后的部门对象

        Raises:
            NotFoundException: 部门不存在时
            BadRequestException: 编码已存在或父部门设置错误时
        """
        dept = await self.dept_crud.get(self.db, id=dept_id)
        if not dept:
            raise NotFoundException(message="部门不存在")

        # 检查编码是否已存在（排除自身）
        if obj_in.code and obj_in.code != dept.code:
            if await self.dept_crud.exists_code(self.db, code=obj_in.code, exclude_id=dept_id):
                raise BadRequestException(message=f"部门编码 '{obj_in.code}' 已存在")

        # 检查父部门设置
        if obj_in.parent_id is not None:
            if obj_in.parent_id == dept_id:
                raise BadRequestException(message="父部门不能是自身")

            # 检查是否形成循环
            children_ids = await self.dept_crud.get_children_ids(self.db, dept_id=dept_id)
            if obj_in.parent_id in children_ids:
                raise BadRequestException(message="父部门不能是自己的子部门")

            # 检查父部门是否存在
            parent = await self.dept_crud.get(self.db, id=obj_in.parent_id)
            if not parent:
                raise NotFoundException(message="父部门不存在")

        updated = await self.dept_crud.update(self.db, db_obj=dept, obj_in=obj_in)
        return self._to_dept_response(updated, children=[])

    @transactional()
    async def delete_dept(self, *, dept_id: UUID) -> DeptResponse:
        """
        删除部门（软删除）。

        Args:
            dept_id: 部门 ID

        Returns:
            删除后的部门对象

        Raises:
            NotFoundException: 部门不存在时
            BadRequestException: 有子部门或关联用户时
        """
        dept = await self.dept_crud.get(self.db, id=dept_id)
        if not dept:
            raise NotFoundException(message="部门不存在")

        # 检查是否有子部门
        if await self.dept_crud.has_children(self.db, dept_id=dept_id):
            raise BadRequestException(message="该部门下有子部门，无法删除")

        # 检查是否有关联用户
        if await self.dept_crud.has_users(self.db, dept_id=dept_id):
            raise BadRequestException(message="该部门下有用户，无法删除")

        success_count, _ = await self.dept_crud.batch_remove(self.db, ids=[dept_id])
        if success_count == 0:
            raise NotFoundException(message="部门删除失败")

        # 刷新对象以获取最新状态（包括 is_deleted=True 和 updated_at）
        await self.db.refresh(dept)
        return self._to_dept_response(dept, children=[])

    @transactional()
    async def batch_delete_depts(self, *, ids: list[UUID], hard_delete: bool = False) -> tuple[int, list[UUID]]:
        """
        批量删除部门。

        Args:
            ids: 部门 ID 列表
            hard_delete: 是否硬删除

        Returns:
            成功数量和失败 ID 列表
        """
        return await self.dept_crud.batch_remove(self.db, ids=ids, hard_delete=hard_delete)

    @transactional()
    async def restore_dept(self, *, dept_id: UUID) -> DeptResponse:
        """
        恢复已删除部门。

        Args:
            dept_id: 部门 ID

        Returns:
            恢复后的部门对象

        Raises:
            NotFoundException: 部门不存在时
        """
        success_count, _ = await self.dept_crud.batch_restore(self.db, ids=[dept_id])
        if success_count == 0:
            raise NotFoundException(message="部门不存在或未被删除")
        dept = await self.dept_crud.get(self.db, id=dept_id)
        if not dept:
            raise NotFoundException(message="部门不存在")
        return self._to_dept_response(dept, children=[])

    @transactional()
    async def batch_restore_depts(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量恢复部门。

        Args:
            ids: 部门 ID 列表

        Returns:
            成功数量和失败 ID 列表
        """
        return await self.dept_crud.batch_restore(self.db, ids=ids)

    @transactional()
    async def hard_delete_dept(self, *, dept_id: UUID) -> None:
        """
        彻底删除部门（硬删除）。

        Args:
            dept_id: 部门 ID

        Raises:
            NotFoundException: 部门不存在或未被软删除
        """
        deleted_dept = await self.dept_crud.get_deleted(self.db, dept_id=dept_id)
        if not deleted_dept:
            raise NotFoundException(message="部门不存在或未被软删除")

        success_count, _ = await self.dept_crud.batch_remove(self.db, ids=[dept_id], hard_delete=True)
        if success_count == 0:
            raise NotFoundException(message="彻底删除失败")

    @transactional()
    async def batch_hard_delete_depts(self, *, ids: list[UUID]) -> tuple[int, list[UUID]]:
        """
        批量彻底删除部门（硬删除）。

        Args:
            ids: 部门 ID 列表

        Returns:
            成功数量和失败 ID 列表
        """
        return await self.dept_crud.batch_remove(self.db, ids=ids, hard_delete=True)
