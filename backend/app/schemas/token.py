"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: token.py
@DateTime: 2025-12-30 15:00:00
@Docs: Token相关的 Schema 定义.
"""

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenAccess(BaseModel):
    access_token: str
    token_type: str


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str | None = None
    type: str | None = None
    iss: str | None = None
    jti: str | None = None
    iat: int | None = None
    exp: int | None = None

    model_config = ConfigDict(extra="ignore")
