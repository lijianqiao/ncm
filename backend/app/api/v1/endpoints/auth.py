"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: auth.py
@DateTime: 2025-12-30 11:45:00
@Docs: 认证 API 接口 (Authentication API).
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api import deps
from app.core.auth_cookies import clear_auth_cookies, generate_csrf_token, set_csrf_cookie, set_refresh_cookie
from app.core.rate_limiter import limiter
from app.schemas.common import ResponseBase
from app.schemas.token import Token, TokenAccess
from app.schemas.user import UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenAccess, summary="用户登录")
@limiter.limit("5/minute")
async def login_access_token(
    response: Response,
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: deps.AuthServiceDep,
) -> TokenAccess:
    """
    OAuth2 兼容的 Token 登录接口。

    验证用户名和密码，返回短期有效的 Access Token 和长期有效的 Refresh Token。
    每个 IP 每分钟最多允许 5 次请求。

    Args:
        request (Request): 请求对象，用于获取 IP 地址。
        background_tasks (BackgroundTasks): 后台任务，用于异步记录登录日志。
        form_data (OAuth2PasswordRequestForm): 表单数据，包含 username 和 password。
        auth_service (AuthService): 认证服务依赖。

    Returns:
        TokenAccess: 包含 Access Token 和 Refresh Token 的响应对象。

    Raises:
        CustomException: 当用户名或密码错误时抛出 400 错误。
    """
    token = await auth_service.login_access_token(
        form_data=form_data, request=request, background_tasks=background_tasks
    )

    # refresh 写入 HttpOnly Cookie；csrf 写入非 HttpOnly Cookie
    set_refresh_cookie(response, token.refresh_token)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return TokenAccess(access_token=token.access_token, token_type=token.token_type)


@router.post("/refresh", response_model=TokenAccess, summary="刷新令牌")
async def refresh_token(
    response: Response,
    request: Request,
    refresh_token: deps.RefreshCookieDep,
    auth_service: deps.AuthServiceDep,
) -> TokenAccess:
    """
    使用 Refresh Token 换取新的 Access Token。

    当 Access Token 过期时，可以使用此接口获取新的 Access Token，而无需重新登录。

    Args:
        token_in (TokenRefresh): 包含 refresh_token 的请求体。
        auth_service (AuthService): 认证服务依赖。

    Returns:
        Token: 包含新的 Access Token 和 (可选) 新的 Refresh Token。

    Raises:
        UnauthorizedException: 当 Refresh Token 无效或过期时抛出 401 错误。
    """
    token: Token = await auth_service.refresh_token(refresh_token=refresh_token, request=request)

    # rotation：下发新的 refresh cookie
    set_refresh_cookie(response, token.refresh_token)

    # 可选：同步轮换 csrf token，缩短被盗用窗口
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return TokenAccess(access_token=token.access_token, token_type=token.token_type)


@router.post("/test-token", response_model=ResponseBase[UserResponse], summary="测试令牌有效性")
async def test_token(current_user: deps.CurrentUser) -> ResponseBase[UserResponse]:
    """
    测试 Access Token 是否有效。

    仅用于验证当前请求携带的 Token 是否合法，并返回当前用户信息。

    Args:
        current_user (User): 当前登录用户 (由依赖自动注入)。

    Returns:
        ResponseBase[UserResponse]: 包含当前用户信息的统一响应结构。
    """
    return ResponseBase(data=UserResponse.model_validate(current_user))


@router.post("/logout", response_model=ResponseBase[None], summary="用户退出登录")
async def logout(
    response: Response,
    current_user: deps.CurrentUser,
    auth_service: deps.AuthServiceDep,
) -> ResponseBase[None]:
    """退出登录。

    后端撤销当前用户的 refresh 会话（Refresh Token Rotation 场景下，撤销后 refresh 将不可再用于刷新）。
    Access Token 理论上仍可能在过期前短暂可用，但前端应立即清理并停止使用。
    Args:
        response (Response): 响应对象，用于清理认证相关的 Cookie。
        current_user (User): 当前登录用户 (由依赖自动注入)。
        auth_service (AuthService): 认证服务依赖。
    Returns:
        ResponseBase[None]: 统一响应结构，data 为空。
    """

    await auth_service.logout(user_id=str(current_user.id))
    clear_auth_cookies(response)
    return ResponseBase(data=None, message="退出登录成功")
