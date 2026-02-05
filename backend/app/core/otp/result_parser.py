"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: result_parser.py
@DateTime: 2026-02-05 09:00:00
@Docs: OTP 结果解析器 (OTP Result Parser).

从 AsyncRunner/Nornir 执行结果中提取 OTP 异常信息。
"""

from typing import TYPE_CHECKING, Any

from app.core.exceptions import OTPRequiredException

from .meta import OtpMetaBuilder
from .types import OtpMeta

if TYPE_CHECKING:
    from nornir.core.task import AggregatedResult


class OtpResultParser:
    """
    OTP 结果解析器。

    从 AsyncRunner 或 Nornir 任务执行结果中提取 OTP 异常信息，
    统一返回 OtpMeta 结构。

    Usage:
        # 从 AggregatedResult 检查 OTP 异常
        meta = OtpResultParser.extract_from_aggregated_result(result)
        if meta:
            # 处理 OTP 需求
            ...

        # 从结果字典列表检查
        meta = OtpResultParser.extract_from_results(results_list)
    """

    @staticmethod
    def extract_from_exception(exc: BaseException | None) -> OtpMeta | None:
        """
        从异常对象中提取 OtpMeta。

        Args:
            exc: 异常对象

        Returns:
            OtpMeta | None: 如果是 OTPRequiredException 则返回 OtpMeta
        """
        if isinstance(exc, OTPRequiredException):
            return OtpMetaBuilder.from_exception(exc)
        return None

    @staticmethod
    def extract_from_aggregated_result(
        result: "AggregatedResult",
    ) -> OtpMeta | None:
        """
        从 Nornir AggregatedResult 中提取第一个 OTP 异常。

        遍历所有主机的结果，查找 OTPRequiredException。

        Args:
            result: Nornir 聚合结果

        Returns:
            OtpMeta | None: 第一个 OTP 异常的元数据，如果没有则返回 None
        """
        for _host_name, host_result in result.items():
            if host_result.failed:
                exc = host_result.exception
                if isinstance(exc, OTPRequiredException):
                    return OtpMetaBuilder.from_exception(exc)
        return None

    @staticmethod
    def extract_from_results(
        results: list[dict[str, Any]],
    ) -> OtpMeta | None:
        """
        从结果字典列表中提取 OTP 元数据。

        适用于 AsyncRunner 返回的结果列表。

        Args:
            results: 结果字典列表

        Returns:
            OtpMeta | None: 第一个包含 OTP 信息的元数据
        """
        for result in results:
            if result.get("otp_required"):
                return OtpMetaBuilder.from_result(result)
            # 检查嵌套的异常信息
            if result.get("error"):
                error_info = result.get("error_info", {})
                if error_info.get("otp_required"):
                    return OtpMetaBuilder.build(
                        credential_id=error_info.get("credential_id"),
                        wait_status=error_info.get("otp_wait_status"),
                        failed_device_ids=[result.get("device_id", "")],
                        task_id=error_info.get("task_id"),
                        message=error_info.get("message"),
                    )
        return None

    @staticmethod
    def collect_failed_device_ids(
        results: list[dict[str, Any]],
    ) -> list[str]:
        """
        收集所有失败的设备 ID。

        Args:
            results: 结果字典列表

        Returns:
            list[str]: 失败设备 ID 列表
        """
        failed_ids = []
        for result in results:
            if result.get("error") or result.get("failed"):
                device_id = result.get("device_id") or result.get("host")
                if device_id:
                    failed_ids.append(str(device_id))
        return failed_ids

    @staticmethod
    def collect_otp_required_device_ids(
        results: list[dict[str, Any]],
    ) -> list[str]:
        """
        收集所有需要 OTP 的设备 ID。

        Args:
            results: 结果字典列表

        Returns:
            list[str]: 需要 OTP 的设备 ID 列表
        """
        otp_device_ids = []
        for result in results:
            if result.get("otp_required"):
                device_id = result.get("device_id") or result.get("host")
                if device_id:
                    otp_device_ids.append(str(device_id))
            # 检查嵌套的异常信息
            error_info = result.get("error_info", {})
            if error_info.get("otp_required"):
                device_id = result.get("device_id") or result.get("host")
                if device_id:
                    otp_device_ids.append(str(device_id))
        return otp_device_ids

    @staticmethod
    def has_otp_exception(result: "AggregatedResult") -> bool:
        """
        快速检查 AggregatedResult 中是否包含 OTP 异常。

        Args:
            result: Nornir 聚合结果

        Returns:
            bool: 是否包含 OTP 异常
        """
        for _host_name, host_result in result.items():
            if host_result.failed:
                if isinstance(host_result.exception, OTPRequiredException):
                    return True
        return False
