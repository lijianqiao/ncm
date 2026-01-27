"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: exceptions.py
@DateTime: 2025-12-30 11:56:00
@Docs: 自定义业务异常 (Custom Domain Exceptions).
"""

from typing import Any
from uuid import UUID


class CustomException(Exception):
    """
    业务逻辑基础异常类。
    """

    def __init__(self, code: int, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFoundException(CustomException):
    """
    资源不存在异常 (404).
    """

    def __init__(self, message: str = "Not Found"):
        super().__init__(code=404, message=message)


class ForbiddenException(CustomException):
    """
    禁止访问异常 (403).
    """

    def __init__(self, message: str = "Forbidden"):
        super().__init__(code=403, message=message)


class UnauthorizedException(CustomException):
    """
    未授权异常 (401).
    """

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(code=401, message=message)


class BadRequestException(CustomException):
    """
    无效请求异常 (400).
    """

    def __init__(self, message: str = "Bad Request"):
        super().__init__(code=400, message=message)


class DomainValidationException(CustomException):
    """领域数据验证错误 (422).

    说明：避免与 pydantic.ValidationError 同名造成混淆。
    """

    def __init__(self, message: str = "Validation Error", details: Any = None):
        super().__init__(code=422, message=message, details=details)


# 向后兼容：旧代码可能仍引用 ValidationError（不推荐继续使用）。
ValidationError = DomainValidationException


# ===== NCM 网络设备管理相关异常 =====


class OTPRequiredException(CustomException):
    """
    需要用户输入 OTP 验证码异常。

    当设备认证类型为 otp_manual 且 Redis 缓存中没有有效的 OTP 时抛出。
    用于支持断点续传：任务暂停等待用户输入新的 OTP 后继续执行。
    """

    def __init__(
        self,
        dept_id: UUID | str,
        device_group: str,
        failed_devices: list[str] | None = None,
        message: str = "需要输入 OTP 验证码",
    ):
        # 存储为字符串，确保可序列化
        self.dept_id_str = str(dept_id)
        self.device_group = device_group
        self.failed_devices = failed_devices or []

        # 同时保留 UUID 类型的属性（用于类型兼容）
        self._dept_id = dept_id if isinstance(dept_id, UUID) else UUID(dept_id)

        super().__init__(
            code=428,  # Precondition Required
            message=message,
            details={
                "dept_id": self.dept_id_str,
                "device_group": device_group,
                "failed_devices": self.failed_devices,
            },
        )

    @property
    def dept_id(self) -> UUID:
        """返回 UUID 类型的 dept_id（向后兼容）。"""
        return self._dept_id

    def __reduce__(self):
        """支持 pickle 序列化（Celery 需要）。"""
        return (
            self.__class__,
            (self.dept_id_str, self.device_group, self.failed_devices, self.message),
        )

    def to_dict(self) -> dict:
        """转换为字典格式（用于 API 返回）。"""
        return {
            "dept_id": self.dept_id_str,
            "device_group": self.device_group,
            "failed_devices": self.failed_devices,
            "message": self.message,
        }


class DeviceCredentialNotFoundException(NotFoundException):
    """
    设备凭据未找到异常。

    当设备的部门+设备分组组合没有对应的凭据配置时抛出。
    """

    def __init__(self, dept_id: UUID | None, device_group: str):
        message = f"未找到凭据配置: dept_id={dept_id}, device_group={device_group}"
        super().__init__(message=message)
