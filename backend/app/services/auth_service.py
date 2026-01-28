"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: auth_service.py
@DateTime: 2025-12-30 13:02:00
@Docs: 认证服务业务逻辑 (Authentication Service Logic) - 包含异步日志。
"""

import uuid
from datetime import timedelta
from hashlib import sha256
from typing import Any

import jwt
from fastapi import BackgroundTasks, Request
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.exceptions import CustomException, UnauthorizedException
from app.core.session_store import remove_online_session, touch_online_session
from app.core.token_store import (
    get_user_refresh_jti,
    revoke_user_access_now,
    revoke_user_refresh,
    set_user_refresh_jti,
)
from app.crud.crud_user import CRUDUser
from app.schemas.token import Token
from app.services.log_service import LogService


class AuthService:
    """
    认证服务类。
    依赖 LogService 和 CRUDUser。
    """

    def __init__(self, db: AsyncSession, log_service: LogService, user_crud: CRUDUser):
        self.db = db
        self.log_service = log_service
        self.user_crud = user_crud

    async def authenticate(self, username: str, password: str) -> Any:
        """
        验证用户名/密码。支持用户名或手机号。
        """
        user = await self.user_crud.get_by_unique_field(self.db, field="username", value=username)
        if not user:
            # 尝试通过手机号查找
            user = await self.user_crud.get_by_unique_field(self.db, field="phone", value=username)

        if not user or not user.is_active or user.is_deleted:
            return None

        if not security.verify_password(password, user.password):
            return None

        return user

    async def login_access_token(self, form_data: Any, request: Request, background_tasks: BackgroundTasks) -> Token:
        """
        处理登录并返回 Token，异步记录日志。
        """
        user = await self.authenticate(form_data.username, form_data.password)
        if not user:
            # 记录失败日志 (异步)
            background_tasks.add_task(
                self.log_service.create_login_log,
                request=request,
                username=form_data.username,
                status=False,
                msg="用户名或密码错误",
            )
            raise CustomException(code=400, message="用户名或密码错误")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(subject=user.id, expires_delta=access_token_expires)
        refresh_token = security.create_refresh_token(subject=user.id)

        # 在线会话：登录时记录并 touch
        try:
            ttl_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
            headers = request.headers
            ip = request.client.host if request.client else None
            user_agent = headers.get("user-agent")
            await touch_online_session(
                user_id=str(user.id),
                username=str(user.username),
                ip=ip,
                user_agent=user_agent,
                ttl_seconds=ttl_seconds,
            )
        except Exception:
            pass

        # Refresh Token 单端有效：记录当前 refresh 的 jti
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                options={"require": ["exp", "sub", "type", "iss"]},
            )
            refresh_jti = payload.get("jti")
            if not refresh_jti:
                refresh_jti = sha256(refresh_token.encode("utf-8")).hexdigest()

            ttl_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
            await set_user_refresh_jti(user_id=str(user.id), jti=str(refresh_jti), ttl_seconds=ttl_seconds)
        except Exception:
            # 不阻塞登录：存储失败时降级为“无服务端会话治理”，但 refresh 时会尽可能校验
            pass

        # 记录成功日志 (异步)
        background_tasks.add_task(
            self.log_service.create_login_log,
            user_id=user.id,
            username=user.username,
            request=request,
            status=True,
            msg="登录成功",
        )

        return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

    async def refresh_token(self, refresh_token: str, *, request: Request | None = None) -> Token:
        """
        刷新 Token。验证 Refresh Token 有效性并返回新的 Access Token。
        """
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                options={"require": ["exp", "sub", "type", "iss"]},
            )
            token_type = payload.get("type")
            if token_type != "refresh":
                raise UnauthorizedException(message="无效的刷新令牌")

            user_id = payload.get("sub")
            if user_id is None:
                raise UnauthorizedException(message="无效的刷新令牌")

            refresh_jti = payload.get("jti")
            if not refresh_jti:
                # 兼容旧 token（没有 jti）：用 token 内容派生一个稳定 id
                refresh_jti = sha256(refresh_token.encode("utf-8")).hexdigest()

        except (InvalidTokenError, Exception) as e:
            raise UnauthorizedException(message="无效的刷新令牌") from e

        # 检查用户是否存在/激活 (可选，但推荐)
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError as e:
            raise UnauthorizedException(message="无效的刷新令牌 (用户ID格式错误)") from e

        user = await self.user_crud.get(self.db, id=user_uuid)
        if not user or not user.is_active:
            raise UnauthorizedException(message="用户不存在或已禁用")

        # 校验 refresh 是否仍为“当前有效”的那一个
        stored_jti = await get_user_refresh_jti(user_id=str(user.id))
        if stored_jti is not None and str(stored_jti) != str(refresh_jti):
            raise UnauthorizedException(message="无效的刷新令牌")

        # 签发新的 Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(subject=user.id, expires_delta=access_token_expires)

        # Refresh Token Rotation：每次刷新都签发新的 refresh，并覆盖存储，使旧 refresh 立即失效
        new_refresh_token = security.create_refresh_token(subject=user.id)
        try:
            new_payload = jwt.decode(
                new_refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                options={"require": ["exp", "sub", "type", "iss"]},
            )
            new_jti = new_payload.get("jti")
            if not new_jti:
                new_jti = sha256(new_refresh_token.encode("utf-8")).hexdigest()

            ttl_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
            await set_user_refresh_jti(user_id=str(user.id), jti=str(new_jti), ttl_seconds=ttl_seconds)
        except Exception:
            # 存储失败时仍返回新 refresh；此时无法做到“单端有效”，但不会影响基本可用性
            pass

        # 在线会话：刷新时 touch（记录最后活跃）
        try:
            ttl_seconds = int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
            ip = None
            user_agent = None
            if request is not None:
                ip = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")
            await touch_online_session(
                user_id=str(user.id),
                username=str(user.username),
                ip=ip,
                user_agent=user_agent,
                ttl_seconds=ttl_seconds,
            )
        except Exception:
            pass

        return Token(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")

    async def logout(self, *, user_id: str) -> None:
        """注销：撤销当前用户 refresh。

        说明：当前实现是“单端 refresh 会话”，撤销后该用户现有 refresh 将失效。
        """
        await revoke_user_refresh(user_id=user_id)
        # 立即使当前所有 access 失效（其他标签页/API 调用立刻 401）
        try:
            await revoke_user_access_now(user_id=user_id)
        except Exception:
            pass
        try:
            await remove_online_session(user_id=user_id)
        except Exception:
            pass
