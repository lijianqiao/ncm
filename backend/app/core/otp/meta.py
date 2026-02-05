"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: meta.py
@DateTime: 2026-02-05 09:00:00
@Docs: OTP 元数据构建器 (OTP Meta Builder).

提供统一的 OTP 元数据构建和序列化方法，减少各层重复的字段拼装逻辑。
"""

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from .types import OtpMeta

if TYPE_CHECKING:
    from app.core.exceptions import OTPRequiredException


class OtpMetaBuilder:
    """
    OTP 元数据构建器。

    提供统一的方法来构建、转换和序列化 OTP 元数据，
    确保各层使用一致的数据结构。

    Usage:
        # 构建基础 OtpMeta
        meta = OtpMetaBuilder.build(
            credential_id=cred_id,
            wait_status="waiting",
            task_id=task_id,
        )

        # 从异常构建
        meta = OtpMetaBuilder.from_exception(otp_exc)

        # 从结果解析
        meta = OtpMetaBuilder.from_result(result_dict)

        # 序列化为 API 响应
        response = OtpMetaBuilder.serialize(meta)
    """

    @staticmethod
    def build(
        credential_id: UUID | str | None,
        *,
        wait_status: str | None = None,
        failed_device_ids: list[str] | None = None,
        pending_device_ids: list[str] | None = None,
        task_id: str | None = None,
        credential_username: str | None = None,
        credential_device_group: str | None = None,
        message: str | None = None,
        otp_wait_timeout: int | None = None,
        otp_cache_ttl: int | None = None,
    ) -> OtpMeta:
        """
        构建 OtpMeta 元数据。

        Args:
            credential_id: 凭据 ID（UUID 或字符串）
            wait_status: 等待状态 (waiting/timeout/ready)
            failed_device_ids: 失败设备 ID 列表
            pending_device_ids: 待处理设备 ID 列表
            task_id: 关联任务 ID
            credential_username: 凭据用户名
            credential_device_group: 凭据设备分组
            message: 提示消息
            otp_wait_timeout: 等待超时时间（秒），默认从配置获取
            otp_cache_ttl: 缓存 TTL（秒），默认从配置获取

        Returns:
            OtpMeta: 统一的 OTP 元数据结构
        """
        from app.core.config import settings

        # 处理 credential_id 为字符串
        cred_id_str: str | None = None
        if credential_id is not None:
            cred_id_str = str(credential_id)

        # 使用配置默认值
        if otp_wait_timeout is None:
            otp_wait_timeout = settings.OTP_WAIT_TIMEOUT_SECONDS
        if otp_cache_ttl is None:
            otp_cache_ttl = settings.OTP_CACHE_TTL_SECONDS

        return OtpMeta(
            otp_required=True,
            otp_credential_id=cred_id_str,
            otp_credential_username=credential_username,
            otp_credential_device_group=credential_device_group,
            otp_wait_status=wait_status,
            otp_failed_device_ids=failed_device_ids or [],
            pending_device_ids=pending_device_ids,
            task_id=task_id,
            otp_wait_timeout=otp_wait_timeout,
            otp_cache_ttl=otp_cache_ttl,
            message=message,
        )

    @staticmethod
    def from_exception(exc: "OTPRequiredException") -> OtpMeta:
        """
        从 OTPRequiredException 异常构建 OtpMeta。

        Args:
            exc: OTP 需要异常

        Returns:
            OtpMeta: 从异常提取的元数据
        """
        details = exc.details or {}
        return OtpMetaBuilder.build(
            credential_id=exc.credential_id_str,
            wait_status=details.get("otp_wait_status"),
            failed_device_ids=exc.failed_devices,
            pending_device_ids=details.get("pending_device_ids"),
            task_id=details.get("task_id"),
            credential_username=exc.credential_username,
            credential_device_group=exc.credential_device_group,
            message=exc.message,
            otp_wait_timeout=details.get("otp_wait_timeout"),
            otp_cache_ttl=details.get("otp_cache_ttl"),
        )

    @staticmethod
    def from_result(result: dict[str, Any]) -> OtpMeta | None:
        """
        从任务结果字典中解析 OtpMeta。

        Args:
            result: 包含可能的 OTP 元数据的结果字典

        Returns:
            OtpMeta | None: 如果结果包含 OTP 信息则返回 OtpMeta，否则返回 None
        """
        # 检查是否包含 OTP 相关字段
        if not result.get("otp_required"):
            return None

        return OtpMetaBuilder.build(
            credential_id=result.get("otp_credential_id"),
            wait_status=result.get("otp_wait_status"),
            failed_device_ids=result.get("otp_failed_device_ids", []),
            pending_device_ids=result.get("pending_device_ids"),
            task_id=result.get("task_id"),
            credential_username=result.get("otp_credential_username"),
            credential_device_group=result.get("otp_credential_device_group"),
            message=result.get("message"),
            otp_wait_timeout=result.get("otp_wait_timeout"),
            otp_cache_ttl=result.get("otp_cache_ttl"),
        )

    @staticmethod
    def merge(base: OtpMeta, override: OtpMeta) -> OtpMeta:
        """
        合并两个 OtpMeta，override 中的非空值会覆盖 base。

        Args:
            base: 基础元数据
            override: 覆盖元数据

        Returns:
            OtpMeta: 合并后的元数据
        """
        merged: dict[str, Any] = dict(base)
        for key, value in override.items():
            if value is not None:
                merged[key] = value
        return cast(OtpMeta, merged)

    @staticmethod
    def serialize(meta: OtpMeta) -> dict[str, Any]:
        """
        序列化 OtpMeta 为 API 响应格式的字典。

        过滤掉 None 值的字段，确保返回干净的响应结构。

        Args:
            meta: OTP 元数据

        Returns:
            dict: 可用于 API 响应的字典
        """
        return {k: v for k, v in meta.items() if v is not None}

    @staticmethod
    def create_success_result(
        credential_id: UUID | str | None = None,
        message: str | None = None,
    ) -> OtpMeta:
        """
        创建不需要 OTP 的成功结果元数据。

        Args:
            credential_id: 凭据 ID
            message: 消息

        Returns:
            OtpMeta: 标记 otp_required=False 的元数据
        """
        cred_id_str = str(credential_id) if credential_id else None
        return OtpMeta(
            otp_required=False,
            otp_credential_id=cred_id_str,
            otp_wait_status=None,
            otp_failed_device_ids=[],
            pending_device_ids=None,
            task_id=None,
            otp_wait_timeout=0,
            otp_cache_ttl=0,
            message=message,
        )

    @staticmethod
    def build_info(
        *,
        credential_id: UUID | str,
        credential_username: str | None = None,
        credential_device_group: str | None = None,
        failed_device_ids: list[str] | None = None,
        wait_status: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """构建 OTP 需求信息字典。

        使用 OtpMetaBuilder 统一构建，确保字段一致性。

        Args:
            credential_id: 凭据 ID
            credential_username: 凭据用户名
            credential_device_group: 凭据设备分组
            failed_device_ids: 失败设备 ID 列表
            wait_status: 等待状态
            message: 消息

        Returns:
            dict[str, Any]: OTP 需求信息字典
        """
        meta = OtpMetaBuilder.build(
            credential_id=credential_id,
            credential_username=credential_username,
            credential_device_group=credential_device_group,
            failed_device_ids=failed_device_ids,
            wait_status=wait_status,
            message=message,
        )
        return OtpMetaBuilder.serialize(meta)

    @staticmethod
    def build_task_result(
        groups: list[dict[str, Any]],
        *,
        next_action: str,
        wait_status: str | None = None,
        task_id: str | None = None,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建 OTP 需求的任务结果。

        Args:
            groups: OTP 分组列表（OtpMeta 格式）
            next_action: 下一步操作
            wait_status: 等待状态
            task_id: 任务 ID
            existing: 已有的结果字典

        Returns:
            dict[str, Any]: 包含 OTP 需求信息的任务结果字典
        """
        from app.core.config import settings

        from .utils import normalize_otp_group

        normalized_groups = [normalize_otp_group(g) for g in groups]

        payload: dict[str, Any] = dict(existing or {})
        payload.update(
            {
                "otp_required": True,
                "otp_credentials": normalized_groups,
                "otp_wait_timeout": settings.OTP_WAIT_TIMEOUT_SECONDS,
                "otp_cache_ttl": settings.OTP_CACHE_TTL_SECONDS,
                "next_action": next_action,
            }
        )
        if wait_status is not None:
            payload["otp_wait_status"] = wait_status
        if task_id is not None:
            payload["task_id"] = task_id
        return payload
