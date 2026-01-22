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

    # NCM 凭据加密（双密钥体系，AES-256 需要 32 字节密钥）
    # 可使用 32 字符 UTF-8 字符串或 64 字符 Hex 编码
    # 生成方法: python -c "import os; print(os.urandom(32).hex())"
    NCM_CREDENTIAL_KEY: str = "changethis_credential_key_32b!!"  # 静态密码加密密钥（32字节）
    NCM_OTP_SEED_KEY: str = "changethis_otp_seed_key_32bytes!"  # OTP 种子加密密钥（独立密钥）
    NCM_SNMP_KEY: str = "changethis_snmp_key_32bytes______"  # SNMP 凭据加密密钥（独立密钥，32字节）

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
    DB_POOL_RECYCLE: int = 3600  # 连接回收时间（秒），防止数据库端断开空闲连接

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
    OTP_CACHE_TTL_SECONDS: int = 30
    OTP_WAIT_TIMEOUT_SECONDS: int = 60  # 等待前端输入新 OTP 的最长时间（秒）

    @computed_field
    @property
    def REDIS_URL(self) -> RedisDsn:
        """
        根据配置生成 Redis 连接 URI.
        """
        from urllib.parse import quote

        # 转义密码中的特殊字符（如 @, :, / 等）
        password_part = f":{quote(self.REDIS_PASSWORD, safe='')}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}")

    # Celery 配置
    CELERY_BROKER_DB: int = 1  # Celery Broker 使用 Redis DB 1
    CELERY_RESULT_DB: int = 2  # Celery 结果存储使用 Redis DB 2

    # Flower 监控配置
    FLOWER_PORT: int = 5555  # Flower Web UI 端口
    FLOWER_BASIC_AUTH: str | None = None  # HTTP Basic Auth, 格式: "user:password"

    # Celery Beat 定时任务配置
    CELERY_BEAT_BACKUP_HOUR: int = 2  # 每日全量备份时间（小时，0-23）
    CELERY_BEAT_BACKUP_MINUTE: int = 0  # 每日全量备份时间（分钟，0-59）
    CELERY_BEAT_INCREMENTAL_HOURS: str = "*/4"  # 增量检查间隔（cron 格式）

    # ARP/MAC 采集配置
    COLLECT_CACHE_TTL: int = 3600  # ARP/MAC 缓存过期时间（秒），默认 1 小时
    CELERY_BEAT_COLLECT_MINUTE: int = 30  # 定时采集分钟（每小时的第几分钟执行）

    # 网络扫描配置
    SCAN_DEFAULT_PORTS: str = "22,23,80,443,161"  # Nmap 默认扫描端口
    SCAN_TIMEOUT: int = 300  # 扫描超时时间（秒）
    SCAN_RATE: int = 1000  # Masscan 扫描速率（packets/sec）
    SCAN_MAX_CONCURRENT_SUBNETS: int = 4  # 资产盘点最大并发扫描子网数
    SCAN_SCHEDULED_SUBNETS: str = ""  # 定时扫描网段列表（逗号分隔，如 "192.168.1.0/24,10.0.0.0/24"）
    CELERY_BEAT_SCAN_HOUR: int = 3  # 定时扫描小时（0-23）
    CELERY_BEAT_SCAN_MINUTE: int = 0  # 定时扫描分钟

    # SNMP 配置（资产发现补全）
    SNMP_TIMEOUT_SECONDS: int = 3  # 单次 SNMP 请求超时（秒）
    SNMP_TIMEOUT_MS: int | None = None  # 兼容毫秒超时配置（优先级高于 SNMP_TIMEOUT_SECONDS）
    SNMP_RETRIES: int = 2  # SNMP 重试次数
    SNMP_MAX_CONCURRENCY: int = 50  # SNMP 并发数（资产补全）

    @model_validator(mode="after")
    def _normalize_snmp_timeout(self):
        if self.SNMP_TIMEOUT_MS is not None and self.SNMP_TIMEOUT_MS > 0:
            self.SNMP_TIMEOUT_SECONDS = max(1, int(self.SNMP_TIMEOUT_MS / 1000))
        return self

    # 拓扑配置
    TOPOLOGY_CACHE_TTL: int = 1800  # 拓扑缓存过期时间（秒），默认 30 分钟
    CELERY_BEAT_TOPOLOGY_HOUR: int = 4  # 定时拓扑刷新小时

    # 异步 SSH 执行配置
    ASYNC_SSH_SEMAPHORE: int = 100  # 最大并发 SSH 连接数
    ASYNC_SSH_TIMEOUT: int = 30  # 单设备 SSH 命令超时（秒）
    ASYNC_SSH_CONNECT_TIMEOUT: int = 10  # SSH 连接超时（秒）

    # Scrapli 连接池配置
    SCRAPLI_POOL_MAX_CONNECTIONS: int = 100  # 连接池最大连接数
    SCRAPLI_POOL_MAX_IDLE_TIME: int = 300  # 连接最大空闲时间（秒）
    SCRAPLI_POOL_MAX_AGE: int = 3600  # 连接最大存活时间（秒）

    # Nornir 任务超时配置
    NORNIR_TASK_TIMEOUT: int = 30  # Nornir 单任务超时时间（秒），用于快速失败

    # 告警配置（Phase 3）
    ALERT_OFFLINE_DAYS_THRESHOLD: int = 3  # 离线告警阈值（天）

    # Webhook 通知（默认不启用）
    ALERT_WEBHOOK_ENABLED: bool = False
    ALERT_WEBHOOK_URL: str = ""

    # 邮件通知（仅提供配置项，默认不启用）
    ALERT_EMAIL_ENABLED: bool = False
    ALERT_EMAIL_HOST: str = ""
    ALERT_EMAIL_PORT: int = 25
    ALERT_EMAIL_USER: str = ""
    ALERT_EMAIL_PASSWORD: str = ""
    ALERT_EMAIL_FROM: str = ""
    ALERT_EMAIL_TO: str = ""

    # MinIO（大配置文件存储）
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ncm"
    MINIO_SECURE: bool = False

    # 备份保留策略（按设备+类型保留最近 N 条，0 表示不限制）
    BACKUP_RETENTION_SCHEDULED_KEEP: int = 500  # 定时备份保留条数
    BACKUP_RETENTION_MANUAL_KEEP: int = 200  # 手动备份保留条数
    BACKUP_RETENTION_PRE_CHANGE_KEEP: int = 200  # 变更前备份保留条数
    BACKUP_RETENTION_POST_CHANGE_KEEP: int = 200  # 变更后备份保留条数
    BACKUP_RETENTION_INCREMENTAL_KEEP: int = 1000  # 增量备份保留条数

    # 备份内容存储分流阈值：小于阈值存 DB，达到或超过阈值存 MinIO
    BACKUP_CONTENT_SIZE_THRESHOLD_BYTES: int = 64 * 1024

    # 备份保留策略（按天数）：默认保留最近 30 天的所有备份类型，0 表示不限制
    # 注意：即便超过天数，也至少保留每台设备 1 条备份（优先保留最新成功备份）
    BACKUP_RETENTION_KEEP_DAYS: int = 30

    # 导入导出（Import/Export）
    IMPORT_EXPORT_TMP_DIR: str = ""  # 空表示使用系统临时目录下的 ncm 子目录
    IMPORT_EXPORT_TTL_HOURS: int = 24  # 导入临时数据默认保留时长（小时）
    IMPORT_EXPORT_MAX_UPLOAD_MB: int = 20  # 上传文件大小限制（MB）

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> RedisDsn:
        """
        Celery 消息代理 URL (使用独立的 Redis DB).
        """
        from urllib.parse import quote

        password_part = f":{quote(self.REDIS_PASSWORD, safe='')}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}")

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> RedisDsn:
        """
        Celery 结果后端 URL (使用独立的 Redis DB).
        """
        from urllib.parse import quote

        password_part = f":{quote(self.REDIS_PASSWORD, safe='')}@" if self.REDIS_PASSWORD else ""
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

        # 4. 检查 NCM 凭据加密密钥
        ncm_default_keys = [
            "changethis_credential_key_32b!!",
            "changethis_otp_seed_key_32bytes!",
            "changethis_snmp_key_32bytes______",
        ]

        def _check_key_length(key: str, name: str) -> None:
            """验证密钥长度（支持 32 字节 UTF-8 或 64 字符 Hex）。"""
            key = key.strip()
            if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                key = key[1:-1].strip()
            # Hex 格式：64 字符 = 32 字节
            if len(key) == 64:
                try:
                    bytes.fromhex(key)
                    return  # 有效的 Hex 密钥
                except ValueError:
                    pass
            # UTF-8 格式：需要正好 32 字节
            if len(key.encode("utf-8")) != 32:
                raise ValueError(
                    f"[BLOCK] {name} 长度无效：需要 32 字节 UTF-8 字符串或 64 字符 Hex 编码，"
                    f"当前 {len(key.encode('utf-8'))} 字节"
                )

        _check_key_length(self.NCM_CREDENTIAL_KEY, "NCM_CREDENTIAL_KEY")
        _check_key_length(self.NCM_OTP_SEED_KEY, "NCM_OTP_SEED_KEY")
        _check_key_length(self.NCM_SNMP_KEY, "NCM_SNMP_KEY")

        if self.NCM_CREDENTIAL_KEY in ncm_default_keys:
            msg = "[安全警告]: NCM_CREDENTIAL_KEY 使用了默认值，请在 .env 中修改。"
            if self.ENVIRONMENT == "production":
                raise ValueError(f"[BLOCK] {msg} 生产环境严禁使用默认密钥！")
            else:
                logging.getLogger(__name__).warning(msg)

        if self.NCM_OTP_SEED_KEY in ncm_default_keys:
            msg = "[安全警告]: NCM_OTP_SEED_KEY 使用了默认值，请在 .env 中修改。"
            if self.ENVIRONMENT == "production":
                raise ValueError(f"[BLOCK] {msg} 生产环境严禁使用默认密钥！")
            else:
                logging.getLogger(__name__).warning(msg)

        if self.NCM_SNMP_KEY in ncm_default_keys:
            msg = "[安全警告]: NCM_SNMP_KEY 使用了默认值，请在 .env 中修改。"
            if self.ENVIRONMENT == "production":
                raise ValueError(f"[BLOCK] {msg} 生产环境严禁使用默认密钥！")
            else:
                logging.getLogger(__name__).warning(msg)

        return self


settings = Settings()
