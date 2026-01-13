"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: preset_templates.py
@DateTime: 2026-01-13 12:45:00
@Docs: 预设模板定义库 - 系统内置的快捷操作模板。
"""

from typing import Any

# 预设模板分类
PRESET_CATEGORY_SHOW = "show"
PRESET_CATEGORY_CONFIG = "config"


# 预设模板定义
PRESET_TEMPLATES: dict[str, dict[str, Any]] = {
    # ===== 查看类操作 =====
    "show_interface": {
        "name": "查看接口状态",
        "description": "查看指定接口的详细状态信息",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display interface {{ params.interface_name }}
{% elif device.vendor == 'huawei' %}
display interface {{ params.interface_name }}
{% elif device.vendor == 'cisco' %}
show interface {{ params.interface_name }}
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "interface_name": {
                    "type": "string",
                    "title": "接口名称",
                    "description": "例如: GigabitEthernet1/0/1, Eth-Trunk1",
                }
            },
            "required": ["interface_name"],
        },
        # 用于 TextFSM 解析的命令映射
        "parse_commands": {
            "h3c": "display interface",
            "huawei": "display interface",
            "cisco": "show interface",
        },
    },
    "show_vlan": {
        "name": "查看 VLAN",
        "description": "查看 VLAN 列表或指定 VLAN 信息",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
{% if params.vlan_id %}
display vlan {{ params.vlan_id }}
{% else %}
display vlan brief
{% endif %}
{% elif device.vendor == 'huawei' %}
{% if params.vlan_id %}
display vlan {{ params.vlan_id }}
{% else %}
display vlan
{% endif %}
{% elif device.vendor == 'cisco' %}
{% if params.vlan_id %}
show vlan id {{ params.vlan_id }}
{% else %}
show vlan brief
{% endif %}
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "vlan_id": {
                    "type": "integer",
                    "title": "VLAN ID",
                    "description": "留空则查看所有 VLAN",
                    "minimum": 1,
                    "maximum": 4094,
                }
            },
            "required": [],
        },
        "parse_commands": {
            "h3c": {"default": "display vlan brief", "with_vlan_id": "display vlan"},
            "huawei": {"default": "display vlan", "with_vlan_id": "display vlan"},
            "cisco": {"default": "show vlan brief", "with_vlan_id": "show vlan id"},
        },
    },
    "show_arp": {
        "name": "查看 ARP 表",
        "description": "查看设备 ARP 表信息",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display arp
{% elif device.vendor == 'huawei' %}
display arp
{% elif device.vendor == 'cisco' %}
show ip arp
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": {
            "h3c": "display arp",
            "huawei": "display arp",
            "cisco": "show ip arp",
        },
    },
    "show_mac": {
        "name": "查看 MAC 表",
        "description": "查看设备 MAC 地址表",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display mac-address
{% elif device.vendor == 'huawei' %}
display mac-address
{% elif device.vendor == 'cisco' %}
show mac address-table
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": {
            "h3c": "display mac-address",
            "huawei": "display mac-address",
            "cisco": "show mac address-table",
        },
    },
    "show_route": {
        "name": "查看路由表",
        "description": "查看设备路由表信息",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display ip routing-table
{% elif device.vendor == 'huawei' %}
display ip routing-table
{% elif device.vendor == 'cisco' %}
show ip route
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": {
            "h3c": "display ip routing-table",
            "huawei": "display ip routing-table",
            "cisco": "show ip route",
        },
    },
    # ===== 配置类操作 =====
    "config_vlan": {
        "name": "配置 VLAN",
        "description": "创建或修改 VLAN 配置",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
vlan {{ params.vlan_id }}
 name {{ params.vlan_name }}
{% if params.description %}
 description {{ params.description }}
{% endif %}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
vlan {{ params.vlan_id }}
 name {{ params.vlan_name }}
{% if params.description %}
 description {{ params.description }}
{% endif %}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
vlan {{ params.vlan_id }}
 name {{ params.vlan_name }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "vlan_id": {
                    "type": "integer",
                    "title": "VLAN ID",
                    "minimum": 1,
                    "maximum": 4094,
                },
                "vlan_name": {
                    "type": "string",
                    "title": "VLAN 名称",
                    "maxLength": 32,
                },
                "description": {
                    "type": "string",
                    "title": "描述",
                    "description": "可选",
                },
            },
            "required": ["vlan_id", "vlan_name"],
        },
        "parse_commands": None,  # 配置类无需解析
    },
    "config_interface_desc": {
        "name": "配置接口描述",
        "description": "修改接口的描述信息",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
interface {{ params.interface_name }}
 description {{ params.description }}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
interface {{ params.interface_name }}
 description {{ params.description }}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
interface {{ params.interface_name }}
 description {{ params.description }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "interface_name": {
                    "type": "string",
                    "title": "接口名称",
                    "description": "例如: GigabitEthernet1/0/1",
                },
                "description": {
                    "type": "string",
                    "title": "接口描述",
                    "maxLength": 80,
                },
            },
            "required": ["interface_name", "description"],
        },
        "parse_commands": None,  # 配置类无需解析
    },
}


def get_preset(preset_id: str) -> dict[str, Any] | None:
    """获取预设模板定义。"""
    return PRESET_TEMPLATES.get(preset_id)


def list_presets() -> list[dict[str, Any]]:
    """列出所有预设模板（简要信息）。"""
    result = []
    for preset_id, preset in PRESET_TEMPLATES.items():
        result.append(
            {
                "id": preset_id,
                "name": preset["name"],
                "description": preset.get("description", ""),
                "category": preset["category"],
                "supported_vendors": preset["supported_vendors"],
            }
        )
    return result
