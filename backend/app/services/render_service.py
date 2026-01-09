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
    def __init__(self) -> None:
        # 说明：配置模板不需要 HTML autoescape
        self._env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)

    def validate_params(self, schema_json: str | None, params: dict[str, Any]) -> None:
        if not schema_json:
            return
        try:
            schema = json.loads(schema_json)
        except json.JSONDecodeError as e:
            raise BadRequestException(f"模板 parameters 不是合法 JSON: {e}") from e

        try:
            jsonschema_validate(instance=params, schema=schema)
        except JSONSchemaValidationError as e:
            raise DomainValidationException(message=f"参数不符合模板 JSON Schema: {e.message}", details=e.schema_path) from e

    def render(self, template: Template, params: dict[str, Any], *, device: Device | None = None) -> str:
        self.validate_params(template.parameters, params)

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

        try:
            j2 = self._env.from_string(template.content)
            return j2.render(**context)
        except TemplateError as e:
            raise BadRequestException(f"模板渲染失败: {e}") from e

