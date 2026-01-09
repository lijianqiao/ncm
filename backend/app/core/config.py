"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: config.py
@DateTime: 2025-12-30 11:30:00
@Docs: 系统配置管理 (System Configuration).
"""

import logging
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    系统配置类，基于 Pydantic Settings 管理环境变量。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # 项目信息
    PROJECT_NAME: str = "Admin RBAC Backend"
    API_V1_STR: str = "/api/v1"

    # 环境
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # 安全
    SECRET_KEY: str = "changethis"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "admin-rbac-backend"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 分钟
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 天
    PASSWORD_COMPLEXITY_ENABLED: bool = True  # 开启后需要大小写+数字+特殊字符且>=8位

    # Auth Cookie/CSRF
    AUTH_REFRESH_COOKIE_NAME: str = "refresh_token"
    AUTH_CSRF_COOKIE_NAME: str = "csrf_token"
    AUTH_CSRF_HEADER_NAME: str = "X-CSRF-Token"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_COOKIE_SECURE: bool = False  # 生产环境应使用 https 并设为 True
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # CORS (跨域资源共享)
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # 数据库
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "admin_rbac"
    DB_POOL_SIZE: int = 5  # 连接池大小
    DB_MAX_OVERFLOW: int = 10  # 最大溢出连接数

    # 初始化超级管理员 (Initial Superuser)
    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_PASSWORD: str = "password"
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PHONE: str = "13800138000"
    FIRST_SUPERUSER_NICKNAME: str = "Administrator"
    FIRST_SUPERUSER_GENDER: Literal["男", "女", "保密"] = "男"

    # 默认角色（创建非超级管理员用户时自动绑定）
    DEFAULT_USER_ROLE_CODE: str = "employee"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    @computed_field
    @property
    def REDIS_URL(self) -> RedisDsn:
        """
        根据配置生成 Redis 连接 URI.
        """
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}")

    # Celery 配置
    CELERY_BROKER_DB: int = 1  # Celery Broker 使用 Redis DB 1
    CELERY_RESULT_DB: int = 2  # Celery 结果存储使用 Redis DB 2

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> RedisDsn:
        """
        Celery 消息代理 URL (使用独立的 Redis DB).
        """
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}")

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> RedisDsn:
        """
        Celery 结果后端 URL (使用独立的 Redis DB).
        """
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_RESULT_DB}")

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """
        根据配置生成 SQLAlchemy 数据库连接 URI。
        """
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @model_validator(mode="after")
    def check_security_settings(self) -> "Settings":
        """
        检查安全配置。在生产环境中，如果有不安全的默认值，则阻止启动。
        """
        # 1. 检查 SECRET_KEY
        if self.SECRET_KEY == "changethis" or len(self.SECRET_KEY) < 12:
            message = "[安全警告]: SECRET_KEY 使用了默认值 'changethis' 或长度过短! 这极不安全，会导致系统易受攻击。"
            if self.ENVIRONMENT in ("production", "staging"):
                raise ValueError(f"[BLOCK] {message} 请并在 .env 中修改 SECRET_KEY。")
            else:
                logging.getLogger(__name__).warning(message)

        # 2. 检查 默认密码 (仅检查显而易见的默认值)
        insecure_passwords = ["password", "admin"]

        if self.POSTGRES_PASSWORD in insecure_passwords:
            msg = f"[安全警告]: 数据库密码使用了弱密码 '{self.POSTGRES_PASSWORD}'。"
            if self.ENVIRONMENT == "production":
                raise ValueError(f"[BLOCK] {msg} 生产环境严禁使用弱密码！")
            else:
                logging.getLogger(__name__).warning(msg)

        if self.FIRST_SUPERUSER_PASSWORD in insecure_passwords:
            msg = f"[安全警告]: 初始管理员密码使用了弱密码 '{self.FIRST_SUPERUSER_PASSWORD}'。"
            if self.ENVIRONMENT == "production":
                raise ValueError(f"[BLOCK] {msg} 生产环境严禁使用弱密码！")
            else:
                logging.getLogger(__name__).warning(msg)

        # 3. 生产/预发环境强制要求配置明确的 CORS 白名单
        if self.ENVIRONMENT in ("production", "staging") and any(str(x) == "*" for x in self.BACKEND_CORS_ORIGINS):
            raise ValueError("[BLOCK] 生产/预发环境禁止将 BACKEND_CORS_ORIGINS 配置为 '*'，请配置具体域名白名单")

        return self


settings = Settings()
