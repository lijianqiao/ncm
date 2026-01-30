"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: render_service.py
@DateTime: 2026-01-09 23:00:00
@Docs: 配置模板渲染服务 (Dry-Run / Render Service).
"""

import json
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as jsonschema_validate

from app.core.exceptions import BadRequestException, DomainValidationException
from app.models.device import Device
from app.models.template import Template


class RenderService:
    """
    配置模板渲染服务类。

    提供配置模板的参数校验和渲染功能。
    """

    def __init__(self) -> None:
        """
        初始化渲染服务。

        说明：配置模板不需要 HTML autoescape
        """
        # 说明：配置模板不需要 HTML autoescape
        self._env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)

    def validate_params(self, schema_json: str | None, params: dict[str, Any]) -> None:
        """
        校验模板参数是否符合 JSON Schema。

        Args:
            schema_json: JSON Schema 字符串（可选）
            params: 待校验的参数

        Raises:
            BadRequestException: Schema 不是合法 JSON
            DomainValidationException: 参数不符合 Schema
        """
        if not schema_json:
            return
        try:
            schema = json.loads(schema_json)
        except json.JSONDecodeError as e:
            raise BadRequestException(f"模板 parameters 不是合法 JSON: {e}") from e

        try:
            jsonschema_validate(instance=params, schema=schema)
        except JSONSchemaValidationError as e:
            raise DomainValidationException(
                message=f"参数不符合模板 JSON Schema: {e.message}",
                details=list(e.schema_path),
            ) from e

    def render(self, template: Template, params: dict[str, Any], *, device: Device | None = None) -> str:
        """
        渲染配置模板。

        Args:
            template: 模板对象
            params: 模板参数
            device: 设备对象（可选，用于提供设备上下文）

        Returns:
            str: 渲染后的配置内容

        Raises:
            BadRequestException: 参数名冲突或模板渲染失败
            DomainValidationException: 参数校验失败
        """
        self.validate_params(template.parameters, params)

        reserved_keys = {"params", "device"}
        conflict_keys = reserved_keys.intersection(params.keys())
        if conflict_keys:
            conflict = ", ".join(sorted(conflict_keys))
            raise BadRequestException(f"参数名与保留关键字冲突: {conflict}")

        context: dict[str, Any] = {
            "params": params,
            "device": None,
        }
        if device is not None:
            context["device"] = {
                "id": str(device.id),
                "name": device.name,
                "ip_address": device.ip_address,
                "vendor": device.vendor,
                "device_group": device.device_group,
                "dept_id": str(device.dept_id) if device.dept_id else None,
            }
        # 兼容顶层变量写法（{{ var }}）与 params.xxx 写法
        # 保护保留键，避免覆盖 context 中的 params/device
        for key, value in params.items():
            if key in {"params", "device"}:
                continue
            if key not in context:
                context[key] = value

        try:
            j2 = self._env.from_string(template.content)
            return j2.render(**context)
        except TemplateError as e:
            raise BadRequestException(f"模板渲染失败: {e}") from e

