"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: exceptions.py
@DateTime: 2025-12-30 11:56:00
@Docs: 自定义业务异常 (Custom Domain Exceptions).
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.core.otp.types import OtpMeta


class CustomException(Exception):
    """
    业务逻辑基础异常类。
    """

    def __init__(self, code: int, message: str, details: Any = None):
        """初始化业务异常。

        Args:
            code (int): HTTP 状态码。
            message (str): 错误消息。
            details (Any): 错误详情，默认为 None。
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFoundException(CustomException):
    """
    资源不存在异常 (404).
    """

    def __init__(self, message: str = "Not Found"):
        """初始化资源不存在异常。

        Args:
            message (str): 错误消息，默认为 "Not Found"。
        """
        super().__init__(code=404, message=message)


class ForbiddenException(CustomException):
    """
    禁止访问异常 (403).
    """

    def __init__(self, message: str = "Forbidden"):
        """初始化禁止访问异常。

        Args:
            message (str): 错误消息，默认为 "Forbidden"。
        """
        super().__init__(code=403, message=message)


class UnauthorizedException(CustomException):
    """
    未授权异常 (401).
    """

    def __init__(self, message: str = "Unauthorized"):
        """初始化未授权异常。

        Args:
            message (str): 错误消息，默认为 "Unauthorized"。
        """
        super().__init__(code=401, message=message)


class BadRequestException(CustomException):
    """
    无效请求异常 (400).
    """

    def __init__(self, message: str = "Bad Request"):
        """初始化无效请求异常。

        Args:
            message (str): 错误消息，默认为 "Bad Request"。
        """
        super().__init__(code=400, message=message)


class DomainValidationException(CustomException):
    """领域数据验证错误 (422).

    说明：避免与 pydantic.ValidationError 同名造成混淆。
    """

    def __init__(self, message: str = "Validation Error", details: Any = None):
        """初始化领域数据验证错误异常。

        Args:
            message (str): 错误消息，默认为 "Validation Error"。
            details (Any): 错误详情，默认为 None。
        """
        super().__init__(code=422, message=message, details=details)


# ===== NCM 网络设备管理相关异常 =====


class OTPRequiredException(CustomException):
    """
    需要用户输入 OTP 验证码异常。

    当设备认证类型为 otp_manual 且 Redis 缓存中没有有效的 OTP 时抛出。
    用于支持断点续传：任务暂停等待用户输入新的 OTP 后继续执行。

    重构说明：
    - 移除了 dept_id/device_group 参数（改为统一使用 credential_id）
    - 使用 OtpMeta 作为数据来源
    """

    def __init__(
        self,
        credential_id: UUID | str | None,
        *,
        failed_devices: list[str] | None = None,
        message: str = "需要输入 OTP 验证码",
        credential_username: str | None = None,
        credential_device_group: str | None = None,
        otp_wait_timeout: int | None = None,
        otp_cache_ttl: int | None = None,
        otp_wait_status: str | None = None,
        task_id: str | None = None,
        pending_device_ids: list[str] | None = None,
    ):
        """初始化 OTP 验证码需求异常。

        Args:
            credential_id: 凭据 ID
            failed_devices: 失败设备 ID 列表
            message: 错误消息
            credential_username: 凭据用户名
            credential_device_group: 凭据设备分组
            otp_wait_timeout: 等待超时时间（秒）
            otp_cache_ttl: 缓存 TTL（秒）
            otp_wait_status: 等待状态
            task_id: 任务 ID
            pending_device_ids: 待处理设备 ID 列表
        """
        # 存储为字符串，确保可序列化
        self.credential_id_str = str(credential_id) if credential_id else None
        self.credential_username = str(credential_username) if credential_username else None
        self.credential_device_group = (
            str(credential_device_group) if credential_device_group else None
        )
        self.failed_devices = failed_devices or []

        if otp_wait_timeout is None or otp_cache_ttl is None:
            from app.core.config import settings

            otp_wait_timeout = otp_wait_timeout or settings.OTP_WAIT_TIMEOUT_SECONDS
            otp_cache_ttl = otp_cache_ttl or settings.OTP_CACHE_TTL_SECONDS

        super().__init__(
            code=428,  # Precondition Required
            message=message,
            details={
                "otp_required": True,
                "credential_id": self.credential_id_str,
                "otp_failed_device_ids": self.failed_devices,
                "pending_device_ids": pending_device_ids,
                "task_id": task_id,
                "otp_wait_timeout": otp_wait_timeout,
                "otp_cache_ttl": otp_cache_ttl,
                "otp_wait_status": otp_wait_status,
            },
        )
        if self.credential_username:
            self.details["otp_credential_username"] = self.credential_username
        if self.credential_device_group:
            self.details["otp_credential_device_group"] = self.credential_device_group

    def __reduce__(self):
        """支持 pickle 序列化（Celery 需要）。

        Returns:
            tuple: 用于 pickle 序列化的元组。
        """
        return (
            self.__class__,
            (self.credential_id_str,),
            {
                "failed_devices": self.failed_devices,
                "message": self.message,
                "credential_username": self.credential_username,
                "credential_device_group": self.credential_device_group,
                "otp_wait_status": self.details.get("otp_wait_status"),
                "task_id": self.details.get("task_id"),
                "pending_device_ids": self.details.get("pending_device_ids"),
                "otp_wait_timeout": self.details.get("otp_wait_timeout"),
                "otp_cache_ttl": self.details.get("otp_cache_ttl"),
            },
        )

    def __setstate__(self, state: dict[str, Any] | None) -> None:
        """恢复 pickle 反序列化的状态。"""
        if state is None:
            return
        self.__init__(
            self.credential_id_str,
            **state,
        )

    def to_dict(self) -> dict:
        """转换为字典格式（用于 API 返回）。

        Returns:
            dict: 包含异常信息的字典。
        """
        return {
            "otp_required": True,
            "credential_id": self.credential_id_str,
            "otp_credential_username": self.credential_username,
            "otp_credential_device_group": self.credential_device_group,
            "otp_failed_device_ids": self.failed_devices,
            "message": self.message,
        }

    def to_meta(self) -> "OtpMeta":
        """转换为 OtpMeta 结构。

        Returns:
            OtpMeta: OTP 元数据
        """
        from app.core.otp import OtpMetaBuilder

        return OtpMetaBuilder.from_exception(self)


class DeviceCredentialNotFoundException(NotFoundException):
    """
    设备凭据未找到异常。

    当设备的部门+设备分组组合没有对应的凭据配置时抛出。
    """

    def __init__(self, dept_id: UUID | None, device_group: str):
        """初始化设备凭据未找到异常。

        Args:
            dept_id (UUID | None): 部门 ID。
            device_group (str): 设备分组。
        """
        message = f"未找到凭据配置: dept_id={dept_id}, device_group={device_group}"
        super().__init__(message=message)
