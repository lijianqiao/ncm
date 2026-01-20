"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: preset_service.py
@DateTime: 2026-01-13 12:45:00
@Docs: 预设模板执行服务。
"""

from typing import Any
from uuid import UUID

from jinja2 import Template as Jinja2Template
from scrapli.exceptions import ScrapliAuthenticationFailed
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.command_policy import normalize_rendered_config, validate_commands
from app.core.enums import AuthType
from app.core.exceptions import BadRequestException, NotFoundException, OTPRequiredException
from app.core.logger import logger
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.network.connection_test import execute_commands_on_device
from app.network.otp_utils import handle_otp_auth_failure_sync
from app.network.platform_config import get_ntc_platform, get_platform_for_vendor
from app.network.preset_templates import PRESET_CATEGORY_CONFIG, get_preset, list_presets
from app.network.textfsm_parser import parse_command_output
from app.schemas.preset import PresetDetail, PresetExecuteResult, PresetInfo
from app.services.base import DeviceCredentialMixin


class PresetService(DeviceCredentialMixin):
    """预设模板服务。"""

    def __init__(self, db: AsyncSession, device_crud: CRUDDevice, credential_crud: CRUDCredential):
        self.db = db
        self.device_crud = device_crud
        self.credential_crud = credential_crud

    async def list_presets(self) -> list[PresetInfo]:
        """列出所有预设模板。"""
        presets = list_presets()
        return [PresetInfo(**p) for p in presets]

    async def get_preset(self, preset_id: str) -> PresetDetail:
        """获取预设详情。"""
        preset = get_preset(preset_id)
        if not preset:
            raise NotFoundException(f"预设 {preset_id} 不存在")
        return PresetDetail(
            id=preset_id,
            name=preset["name"],
            description=preset.get("description", ""),
            category=preset["category"],
            supported_vendors=preset["supported_vendors"],
            parameters_schema=preset["parameters_schema"],
        )

    async def execute_preset(
        self,
        preset_id: str,
        device_id: UUID,
        params: dict[str, Any],
    ) -> PresetExecuteResult:
        """执行预设操作。"""
        # 1. 获取预设定义
        preset = get_preset(preset_id)
        if not preset:
            raise NotFoundException(f"预设 {preset_id} 不存在")

        # 2. 获取设备
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException("设备不存在")

        # 3. 检查厂商支持
        if device.vendor not in preset["supported_vendors"]:
            raise BadRequestException(
                f"预设 {preset['name']} 不支持厂商 {device.vendor}，支持的厂商: {preset['supported_vendors']}"
            )

        self._validate_params(preset, params)

        # 4. 渲染命令
        try:
            template = Jinja2Template(preset["template"])
            device_context = {
                "id": str(device.id),
                "name": device.name,
                "ip_address": device.ip_address,
                "vendor": device.vendor,
                "platform": device.platform or get_platform_for_vendor(device.vendor),
            }
            rendered = template.render(device=device_context, params=params)
            commands = normalize_rendered_config(rendered)
            if not commands:
                return PresetExecuteResult(success=False, error_message="渲染结果为空")
        except Exception as e:
            logger.error("预设模板渲染失败", preset=preset_id, error=str(e))
            return PresetExecuteResult(
                success=False,
                error_message=f"模板渲染失败: {e}",
            )

        # 5. 获取凭据
        try:
            cred = await self._get_device_credential(device)
        except OTPRequiredException as e:
            return PresetExecuteResult(
                success=False,
                error_message=e.message,
                otp_required=True,
                otp_required_groups=[{"dept_id": str(e.dept_id), "device_group": str(e.device_group)}],
                expires_in=None,
                next_action="cache_otp_and_retry_execute_preset",
            )
        except Exception as e:
            return PresetExecuteResult(
                success=False,
                error_message=f"获取凭据失败: {e}",
            )

        # 6. 执行命令
        try:
            platform = device.platform or get_platform_for_vendor(device.vendor)

            # 配置类增加黑名单校验（不启用严格白名单，避免各厂商关键字差异导致误伤）
            if preset["category"] == PRESET_CATEGORY_CONFIG:
                validate_commands(commands, strict_allowlist=False)

            result = await execute_commands_on_device(
                host=device.ip_address,
                username=cred.username,
                password=cred.password,
                commands=commands,
                platform=platform,
                port=device.ssh_port or 22,
                is_config=preset["category"] == PRESET_CATEGORY_CONFIG,
            )
            if not result.get("success"):
                return PresetExecuteResult(success=False, error_message=result.get("error") or "命令执行失败")

            raw_output = str(result.get("output") or "")

        except ScrapliAuthenticationFailed as e:
            # 认证失败：调用 OTP 处理逻辑
            host_data = {
                "auth_type": "otp_manual"
                if device.auth_type and AuthType(device.auth_type) == AuthType.OTP_MANUAL
                else "static",
                "dept_id": str(device.dept_id) if device.dept_id else None,
                "device_group": device.device_group,
                "device_id": str(device.id),
            }
            try:
                handle_otp_auth_failure_sync(host_data, e)
            except OTPRequiredException as otp_e:
                return PresetExecuteResult(
                    success=False,
                    error_message=otp_e.message,
                    otp_required=True,
                    otp_required_groups=[{"dept_id": str(otp_e.dept_id), "device_group": str(otp_e.device_group)}],
                    expires_in=None,
                    next_action="cache_otp_and_retry_execute_preset",
                )
            raise

        except Exception as e:
            logger.error("预设命令执行失败", preset=preset_id, device=str(device_id), error=str(e))
            return PresetExecuteResult(
                success=False,
                error_message=f"命令执行失败: {e}",
            )

        # 7. 结构化解析（仅查看类）
        parsed_output = None
        parse_error = None
        parse_commands = preset.get("parse_commands")

        if parse_commands and device.vendor in parse_commands:
            try:
                parse_cmd = self._select_parse_command(
                    preset_id=preset_id,
                    params=params,
                    parse_cmd_value=parse_commands[device.vendor],
                )
                if not parse_cmd:
                    raise ValueError("未配置可用的解析命令")
                ntc_platform = get_ntc_platform(platform)
                parsed_output = parse_command_output(
                    platform=ntc_platform,
                    command=parse_cmd,
                    output=raw_output,
                )
                if raw_output.strip() and parsed_output == []:
                    parse_error = "未匹配到解析模板（或输出不符合模板）"
            except Exception as e:
                parse_error = f"解析失败: {e}"
                logger.warning("预设输出解析失败", preset=preset_id, error=str(e))

        return PresetExecuteResult(
            success=True,
            raw_output=raw_output,
            parsed_output=parsed_output,
            parse_error=parse_error,
        )

    def _validate_params(self, preset: dict[str, Any], params: dict[str, Any]) -> None:
        schema = preset.get("parameters_schema") or {}
        required = schema.get("required") or []
        properties = schema.get("properties") or {}

        if not isinstance(params, dict):
            raise BadRequestException("params 必须为对象")

        for key in required:
            if key not in params or params.get(key) in (None, ""):
                raise BadRequestException(f"缺少必填参数: {key}")

        # 简单类型/范围校验 + 防止换行注入
        for key, rule in properties.items():
            if key not in params:
                continue
            value = params.get(key)
            if value is None:
                continue

            expected_type = rule.get("type")
            if expected_type == "string":
                if not isinstance(value, str):
                    raise BadRequestException(f"参数 {key} 类型错误，必须为字符串")
                if "\n" in value or "\r" in value:
                    raise BadRequestException(f"参数 {key} 不允许包含换行")
                max_length = rule.get("maxLength")
                if isinstance(max_length, int) and len(value) > max_length:
                    raise BadRequestException(f"参数 {key} 长度超限")

            elif expected_type == "integer":
                if not isinstance(value, int):
                    raise BadRequestException(f"参数 {key} 类型错误，必须为整数")
                minimum = rule.get("minimum")
                maximum = rule.get("maximum")
                if isinstance(minimum, int) and value < minimum:
                    raise BadRequestException(f"参数 {key} 不能小于 {minimum}")
                if isinstance(maximum, int) and value > maximum:
                    raise BadRequestException(f"参数 {key} 不能大于 {maximum}")

    def _select_parse_command(self, *, preset_id: str, params: dict[str, Any], parse_cmd_value: Any) -> str:
        """根据预设与参数选择用于解析的命令（用于 ntc-templates/TextFSM）。"""
        if isinstance(parse_cmd_value, str):
            return parse_cmd_value

        # 兼容 parse_commands[vendor] 为 dict 的场景（例如 VLAN：brief vs detail 输出差异）
        if isinstance(parse_cmd_value, dict):
            if preset_id == "show_vlan":
                has_vlan_id = params.get("vlan_id") not in (None, "")
                key = "with_vlan_id" if has_vlan_id else "default"
                v = parse_cmd_value.get(key)
                if isinstance(v, str) and v:
                    return v
            v = parse_cmd_value.get("default")
            if isinstance(v, str) and v:
                return v

        # 兜底：不给解析，直接让上层走解析失败提示
        return ""
