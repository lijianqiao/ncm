"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: deps.py
@DateTime: 2025-12-30 12:05:00
@Docs: FastAPI 依赖注入模块 (Database Session & Auth Dependency).
"""

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated
from urllib.parse import urlparse

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import cache as cache_module
from app.core.auth_cookies import csrf_cookie_name, csrf_header_name, refresh_cookie_name
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.logger import logger
from app.core.token_store import get_user_revoked_after
from app.crud.crud_alert import CRUDAlert
from app.crud.crud_alert import alert_crud as alert_instance
from app.crud.crud_backup import CRUDBackup
from app.crud.crud_backup import backup as backup_instance
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_credential import credential as credential_instance
from app.crud.crud_dept import CRUDDept
from app.crud.crud_device import CRUDDevice
from app.crud.crud_device import device as device_instance
from app.crud.crud_discovery import CRUDDiscovery
from app.crud.crud_discovery import discovery_crud as discovery_instance
from app.crud.crud_inventory_audit import CRUDInventoryAudit
from app.crud.crud_inventory_audit import inventory_audit_crud as inventory_audit_crud_instance
from app.crud.crud_log import (
    CRUDLoginLog,
    CRUDOperationLog,
)
from app.crud.crud_log import (
    login_log as login_log_crud_global,
)
from app.crud.crud_log import (
    operation_log as operation_log_crud_global,
)
from app.crud.crud_menu import CRUDMenu
from app.crud.crud_menu import menu as menu_crud_global
from app.crud.crud_role import CRUDRole
from app.crud.crud_role import role as role_crud_global
from app.crud.crud_task import CRUDTask
from app.crud.crud_task import task_crud as task_crud_instance
from app.crud.crud_task_approval import CRUDTaskApprovalStep
from app.crud.crud_task_approval import task_approval_crud as task_approval_crud_instance
from app.crud.crud_template import CRUDTemplate
from app.crud.crud_template import template as template_instance
from app.crud.crud_template_approval import (
    CRUDTemplateApprovalStep,
)
from app.crud.crud_template_approval import (
    template_approval_crud as template_approval_crud_instance,
)
from app.crud.crud_topology import CRUDTopology
from app.crud.crud_topology import topology_crud as topology_instance
from app.crud.crud_user import CRUDUser
from app.crud.crud_user import user as user_crud_global
from app.models.dept import Department
from app.models.rbac import Role
from app.models.user import User
from app.schemas.token import TokenPayload
from app.services.alert_service import AlertService
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.collect_service import CollectService
from app.services.credential_service import CredentialService
from app.services.dashboard_service import DashboardService
from app.services.deploy_service import DeployService
from app.services.dept_service import DeptService
from app.services.device_service import DeviceService
from app.services.diff_service import DiffService
from app.services.discovery_service import DiscoveryService
from app.services.inventory_audit_service import InventoryAuditService
from app.services.log_service import LogService
from app.services.menu_service import MenuService
from app.services.permission_service import PermissionService
from app.services.preset_service import PresetService
from app.services.render_service import RenderService
from app.services.role_service import RoleService
from app.services.scan_service import ScanService
from app.services.session_service import SessionService
from app.services.template_service import TemplateService
from app.services.topology_service import TopologyService
from app.services.user_service import UserService

# -----------------------

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    获取异步数据库会话依赖
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(request: Request, session: SessionDep, token: TokenDep) -> User:
    """
    解析 Token 并获取当前登录用户
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "type", "iss"]},
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError) as e:
        logger.error(f"Token 验证失败: {str(e)}", error=str(e))
        raise UnauthorizedException(message="无法验证凭据 (Token 无效)") from e

    if token_data.type != "access":
        raise UnauthorizedException(message="无法验证凭据 (Token 类型错误)")

    if token_data.sub is None:
        logger.error("Token 缺少 sub 字段")
        raise UnauthorizedException(message="无法验证凭据 (Token 缺失 sub)")

    # 直接查询数据库获取用户
    try:
        user_uuid = uuid.UUID(token_data.sub)
    except ValueError as e:
        logger.error(f"Token 解析失败: {str(e)}", error=str(e))
        raise UnauthorizedException(message="Token 无效 (用户ID格式错误)") from e

    # 预加载 roles->menus，便于计算权限集合且避免后续惰性加载
    result = await session.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.menus))
        .where(User.id == user_uuid)
        .execution_options(populate_existing=True)
    )
    user = result.scalars().first()

    if not user:
        logger.error(f"未找到用户 {token_data.sub}")
        raise NotFoundException(message="用户不存在")
    if not user.is_active:
        raise ForbiddenException(message="用户已被禁用")

    # 即时会话失效：若用户被强制下线或注销，设置了 revoked_after，则 iat 早于该时间的 access 立即失效
    try:
        revoked_after = await get_user_revoked_after(user_id=str(user.id))
        if revoked_after is not None and token_data.iat is not None:
            try:
                token_iat = int(token_data.iat)
            except Exception:
                token_iat = None
            if token_iat is not None and token_iat <= int(revoked_after):
                raise UnauthorizedException(message="登录状态已失效，请重新登录")
    except UnauthorizedException:
        raise
    except Exception as e:
        # 存储不可用时不阻断请求，但记录告警
        logger.warning(f"revoked_after 校验失败: {e}")

    # 将用户信息绑定到 request state，供中间件使用(存储简单值避免 Session 关闭后的 DetachedInstanceError)
    request.state.user_id = str(user.id)
    request.state.username = user.username

    # 计算并缓存权限集合：v1:user:permissions:{user_id}
    if user.is_superuser:
        request.state.permissions = {"*"}
        return user

    permissions_cache_key = f"v1:user:permissions:{user.id}"
    permissions: set[str] = set()

    if cache_module.redis_client is not None:
        try:
            cached = await cache_module.redis_client.get(permissions_cache_key)
            if cached:
                permissions = set(json.loads(cached))
        except Exception as e:
            logger.warning(f"权限缓存读取失败: {e}")

    if not permissions:
        for role in user.roles:
            for menu in role.menus:
                if menu.permission:
                    permissions.add(menu.permission)

        if cache_module.redis_client is not None:
            try:
                await cache_module.redis_client.setex(
                    permissions_cache_key, 300, json.dumps(sorted(permissions), ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"权限缓存写入失败: {e}")

    request.state.permissions = permissions
    return user


def require_permissions(required_permissions: list[str]):
    """权限校验依赖：超级管理员放行；否则要求权限集合包含 required_permissions"""

    async def _checker(request: Request, current_user: CurrentUser) -> User:
        if current_user.is_superuser:
            return current_user

        perms = getattr(request.state, "permissions", set())
        if not isinstance(perms, set):
            perms = set(perms)

        if not set(required_permissions).issubset(perms):
            raise ForbiddenException(message="权限不足")
        return current_user

    return _checker


CurrentUser = Annotated[User, Depends(get_current_user)]


def _is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True

    allowed = settings.BACKEND_CORS_ORIGINS
    if any(str(x) == "*" for x in allowed):
        return True

    return origin in set(allowed)


def _extract_origin_from_referer(referer: str) -> str | None:
    if not referer:
        return None
    try:
        u = urlparse(referer)
        if not u.scheme or not u.netloc:
            return None
        return f"{u.scheme}://{u.netloc}"
    except Exception:
        return None


async def require_refresh_cookie_and_csrf(request: Request) -> str:
    """Refresh Cookie + CSRF 校验依赖

    说明：
    - refresh_token 放在 HttpOnly Cookie，因 refresh 接口属于 Cookie 认证，需 CSRF 防护
    - CSRF 采用双提取 Cookie：csrf_token Cookie(非 HttpOnly) + X-CSRF-Token 请求头
    - 额外校验 Origin/Referer（若存在且配置了白名单）
    """

    refresh_token = request.cookies.get(refresh_cookie_name())
    if not refresh_token:
        raise UnauthorizedException(message="缺少刷新令牌")

    csrf_cookie = request.cookies.get(csrf_cookie_name())
    csrf_header = request.headers.get(csrf_header_name())
    if not csrf_cookie or not csrf_header or str(csrf_cookie) != str(csrf_header):
        raise ForbiddenException(message="CSRF 校验失败")

    origin = request.headers.get("origin")
    if origin:
        if not _is_origin_allowed(origin):
            raise ForbiddenException(message="CSRF 校验失败 (Origin 不允许)")
    else:
        referer = request.headers.get("referer")
        if referer:
            ref_origin = _extract_origin_from_referer(referer)
            if ref_origin and not _is_origin_allowed(ref_origin):
                raise ForbiddenException(message="CSRF 校验失败 (Referer 不允许)")

    return str(refresh_token)


RefreshCookieDep = Annotated[str, Depends(require_refresh_cookie_and_csrf)]


async def get_current_active_superuser(current_user: CurrentUser) -> User:
    """
    检查当前用户是否为超级管理员
    """
    if not current_user.is_superuser:
        raise ForbiddenException(message="权限不足: 需要超级管理员权限")
    return current_user


# ==================== CRUD 依赖注入 ====================


def get_alert_crud() -> CRUDAlert:
    return alert_instance


def get_backup_crud() -> CRUDBackup:
    return backup_instance


def get_credential_crud() -> CRUDCredential:
    return credential_instance


def get_dept_crud() -> CRUDDept:
    return CRUDDept(Department)


def get_device_crud() -> CRUDDevice:
    return device_instance


def get_discovery_crud() -> CRUDDiscovery:
    return discovery_instance


def get_inventory_audit_crud() -> CRUDInventoryAudit:
    return inventory_audit_crud_instance


def get_login_log_crud() -> CRUDLoginLog:
    return login_log_crud_global


def get_menu_crud() -> CRUDMenu:
    return menu_crud_global


def get_operation_log_crud() -> CRUDOperationLog:
    return operation_log_crud_global


def get_role_crud() -> CRUDRole:
    return role_crud_global


def get_task_approval_crud() -> CRUDTaskApprovalStep:
    return task_approval_crud_instance


def get_task_crud() -> CRUDTask:
    return task_crud_instance


def get_template_approval_crud() -> CRUDTemplateApprovalStep:
    return template_approval_crud_instance


def get_template_crud() -> CRUDTemplate:
    return template_instance


def get_topology_crud() -> CRUDTopology:
    return topology_instance


def get_user_crud() -> CRUDUser:
    return user_crud_global


AlertCRUDDep = Annotated[CRUDAlert, Depends(get_alert_crud)]
BackupCRUDDep = Annotated[CRUDBackup, Depends(get_backup_crud)]
CredentialCRUDDep = Annotated[CRUDCredential, Depends(get_credential_crud)]
DeptCRUDDep = Annotated[CRUDDept, Depends(get_dept_crud)]
DeviceCRUDDep = Annotated[CRUDDevice, Depends(get_device_crud)]
DiscoveryCRUDDep = Annotated[CRUDDiscovery, Depends(get_discovery_crud)]
InventoryAuditCRUDDep = Annotated[CRUDInventoryAudit, Depends(get_inventory_audit_crud)]
LoginLogCRUDDep = Annotated[CRUDLoginLog, Depends(get_login_log_crud)]
MenuCRUDDep = Annotated[CRUDMenu, Depends(get_menu_crud)]
OperationLogCRUDDep = Annotated[CRUDOperationLog, Depends(get_operation_log_crud)]
RoleCRUDDep = Annotated[CRUDRole, Depends(get_role_crud)]
TaskApprovalCRUDDep = Annotated[CRUDTaskApprovalStep, Depends(get_task_approval_crud)]
TaskCRUDDep = Annotated[CRUDTask, Depends(get_task_crud)]
TemplateApprovalCRUDDep = Annotated[CRUDTemplateApprovalStep, Depends(get_template_approval_crud)]
TemplateCRUDDep = Annotated[CRUDTemplate, Depends(get_template_crud)]
TopologyCRUDDep = Annotated[CRUDTopology, Depends(get_topology_crud)]
UserCRUDDep = Annotated[CRUDUser, Depends(get_user_crud)]


# ==================== Service 依赖注入 ====================


def get_alert_service(db: SessionDep, alert_crud: AlertCRUDDep) -> AlertService:
    return AlertService(db, alert_crud)


def get_backup_service(
    db: SessionDep,
    backup_crud: BackupCRUDDep,
    device_crud: DeviceCRUDDep,
    credential_crud: CredentialCRUDDep,
) -> BackupService:
    return BackupService(db, backup_crud, device_crud, credential_crud)


def get_collect_service(
    db: SessionDep,
    device_crud: DeviceCRUDDep,
    credential_crud: CredentialCRUDDep,
) -> CollectService:
    return CollectService(db, device_crud, credential_crud)


def get_credential_service(db: SessionDep, credential_crud: CredentialCRUDDep) -> CredentialService:
    return CredentialService(db, credential_crud)


def get_dashboard_service(
    db: SessionDep,
    user_crud: UserCRUDDep,
    role_crud: RoleCRUDDep,
    menu_crud: MenuCRUDDep,
    login_log_crud: LoginLogCRUDDep,
    operation_log_crud: OperationLogCRUDDep,
) -> DashboardService:
    return DashboardService(db, user_crud, role_crud, menu_crud, login_log_crud, operation_log_crud)


def get_deploy_service(
    db: SessionDep,
    task_crud: TaskCRUDDep,
    task_approval_crud: TaskApprovalCRUDDep,
    device_crud: DeviceCRUDDep,
    credential_crud: CredentialCRUDDep,
) -> DeployService:
    return DeployService(db, task_crud, task_approval_crud, device_crud, credential_crud)


def get_dept_service(db: SessionDep, dept_crud: DeptCRUDDep) -> DeptService:
    return DeptService(db, dept_crud)


def get_device_service(db: SessionDep, device_crud: DeviceCRUDDep, credential_crud: CredentialCRUDDep) -> DeviceService:
    return DeviceService(db, device_crud, credential_crud)


def get_diff_service(db: SessionDep, backup_crud: BackupCRUDDep) -> DiffService:
    return DiffService(db, backup_crud)


def get_inventory_audit_service(db: SessionDep, inventory_audit_crud: InventoryAuditCRUDDep) -> InventoryAuditService:
    return InventoryAuditService(db, inventory_audit_crud)


def get_log_service(
    db: SessionDep, login_log_crud: LoginLogCRUDDep, operation_log_crud: OperationLogCRUDDep
) -> LogService:
    return LogService(db, login_log_crud, operation_log_crud)


def get_auth_service(
    db: SessionDep,
    log_service: Annotated[LogService, Depends(get_log_service)],
    user_crud: UserCRUDDep,
) -> AuthService:
    return AuthService(db, log_service, user_crud)


def get_menu_service(db: SessionDep, menu_crud: MenuCRUDDep) -> MenuService:
    return MenuService(db, menu_crud)


def get_permission_service() -> PermissionService:
    return PermissionService()


def get_preset_service(db: SessionDep, device_crud: DeviceCRUDDep, credential_crud: CredentialCRUDDep) -> PresetService:
    return PresetService(db, device_crud, credential_crud)


def get_render_service() -> RenderService:
    return RenderService()


def get_role_service(db: SessionDep, role_crud: RoleCRUDDep, menu_crud: MenuCRUDDep) -> RoleService:
    return RoleService(db, role_crud, menu_crud)


def get_scan_service(discovery_crud: DiscoveryCRUDDep, device_crud: DeviceCRUDDep) -> ScanService:
    return ScanService(discovery_crud=discovery_crud, device_crud=device_crud)


def get_session_service(db: SessionDep, user_crud: UserCRUDDep) -> SessionService:
    return SessionService(db, user_crud)


def get_template_service(
    db: SessionDep, template_crud: TemplateCRUDDep, template_approval_crud: TemplateApprovalCRUDDep
) -> TemplateService:
    return TemplateService(db, template_crud, template_approval_crud)


def get_topology_service(topology_crud: TopologyCRUDDep, device_crud: DeviceCRUDDep) -> TopologyService:
    return TopologyService(
        topology_crud=topology_crud,
        device_crud=device_crud,
        redis_client=cache_module.redis_client,
    )


def get_user_service(db: SessionDep, user_crud: UserCRUDDep, role_crud: RoleCRUDDep) -> UserService:
    return UserService(db, user_crud, role_crud)


def get_discovery_service(db: SessionDep, discovery_crud: DiscoveryCRUDDep) -> DiscoveryService:
    return DiscoveryService(db, discovery_crud)


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
BackupServiceDep = Annotated[BackupService, Depends(get_backup_service)]
CollectServiceDep = Annotated[CollectService, Depends(get_collect_service)]
CredentialServiceDep = Annotated[CredentialService, Depends(get_credential_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
DeployServiceDep = Annotated[DeployService, Depends(get_deploy_service)]
DeptServiceDep = Annotated[DeptService, Depends(get_dept_service)]
DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]
DiffServiceDep = Annotated[DiffService, Depends(get_diff_service)]
DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]
InventoryAuditServiceDep = Annotated[InventoryAuditService, Depends(get_inventory_audit_service)]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
MenuServiceDep = Annotated[MenuService, Depends(get_menu_service)]
PermissionServiceDep = Annotated[PermissionService, Depends(get_permission_service)]
PresetServiceDep = Annotated[PresetService, Depends(get_preset_service)]
RenderServiceDep = Annotated[RenderService, Depends(get_render_service)]
RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]
ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]
SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
TopologyServiceDep = Annotated[TopologyService, Depends(get_topology_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
