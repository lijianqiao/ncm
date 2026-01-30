"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: token.py
@DateTime: 2025-12-30 15:00:00
@Docs: Token相关的 Schema 定义.
"""

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    """Token 响应 Schema。

    用于返回访问令牌和刷新令牌的响应体。

    Attributes:
        access_token (str): 访问令牌。
        refresh_token (str): 刷新令牌。
        token_type (str): 令牌类型（通常是 "bearer"）。
    """

    access_token: str
    refresh_token: str
    token_type: str


class TokenAccess(BaseModel):
    """访问令牌响应 Schema。

    用于返回访问令牌的响应体。

    Attributes:
        access_token (str): 访问令牌。
        token_type (str): 令牌类型（通常是 "bearer"）。
    """

    access_token: str
    token_type: str


class TokenRefresh(BaseModel):
    """刷新令牌请求 Schema。

    用于刷新访问令牌的请求体。

    Attributes:
        refresh_token (str): 刷新令牌。
    """

    refresh_token: str


class TokenPayload(BaseModel):
    """Token 载荷 Schema。

    用于解析 JWT Token 的载荷信息。

    Attributes:
        sub (str | None): 主题（通常是用户 ID）。
        type (str | None): 令牌类型。
        iss (str | None): 签发者。
        jti (str | None): JWT ID。
        iat (int | None): 签发时间（Unix 时间戳）。
        exp (int | None): 过期时间（Unix 时间戳）。
    """

    sub: str | None = None
    type: str | None = None
    iss: str | None = None
    jti: str | None = None
    iat: int | None = None
    exp: int | None = None

    model_config = ConfigDict(extra="ignore")
