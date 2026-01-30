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
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
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
        "template": """interface {{ params.interface_name }}
description {{ params.description }}""",
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
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["interface_name", "description"],
        },
        "parse_commands": None,
    },
    "config_interface_vlan": {
        "name": "配置接口 VLAN",
        "description": "将接口加入指定 VLAN（Access 或 Trunk）",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
interface {{ params.interface_name }}
{% if params.port_type == 'access' %}
port link-type access
port access vlan {{ params.vlan_id }}
{% elif params.port_type == 'trunk' %}
port link-type trunk
port trunk permit vlan {{ params.vlan_id }}
{% endif %}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
interface {{ params.interface_name }}
{% if params.port_type == 'access' %}
port link-type access
port default vlan {{ params.vlan_id }}
{% elif params.port_type == 'trunk' %}
port link-type trunk
port trunk allow-pass vlan {{ params.vlan_id }}
{% endif %}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
interface {{ params.interface_name }}
{% if params.port_type == 'access' %}
switchport mode access
switchport access vlan {{ params.vlan_id }}
{% elif params.port_type == 'trunk' %}
switchport mode trunk
switchport trunk allowed vlan add {{ params.vlan_id }}
{% endif %}
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
                "vlan_id": {
                    "type": "integer",
                    "title": "VLAN ID",
                    "minimum": 1,
                    "maximum": 4094,
                },
                "port_type": {
                    "type": "string",
                    "title": "端口类型",
                    "enum": ["access", "trunk"],
                    "description": "access=接入端口, trunk=中继端口",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["interface_name", "vlan_id", "port_type"],
        },
        "parse_commands": None,
    },
    "config_interface_ip": {
        "name": "配置接口 IP",
        "description": "为三层接口配置 IP 地址",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
interface {{ params.interface_name }}
ip address {{ params.ip_address }} {{ params.netmask }}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
interface {{ params.interface_name }}
ip address {{ params.ip_address }} {{ params.netmask }}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
interface {{ params.interface_name }}
ip address {{ params.ip_address }} {{ params.netmask }}
no shutdown
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "interface_name": {
                    "type": "string",
                    "title": "接口名称",
                    "description": "例如: Vlanif100, GigabitEthernet0/0/1",
                },
                "ip_address": {
                    "type": "string",
                    "title": "IP 地址",
                    "format": "ipv4",
                    "description": "例如: 192.168.1.1",
                },
                "netmask": {
                    "type": "string",
                    "title": "子网掩码",
                    "description": "例如: 255.255.255.0",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["interface_name", "ip_address", "netmask"],
        },
        "parse_commands": None,
    },
    "config_interface_shutdown": {
        "name": "接口启用/禁用",
        "description": "启用或禁用接口",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
interface {{ params.interface_name }}
{% if params.enable %}
undo shutdown
{% else %}
shutdown
{% endif %}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
interface {{ params.interface_name }}
{% if params.enable %}
undo shutdown
{% else %}
shutdown
{% endif %}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
interface {{ params.interface_name }}
{% if params.enable %}
no shutdown
{% else %}
shutdown
{% endif %}
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
                "enable": {
                    "type": "boolean",
                    "title": "启用接口",
                    "description": "true=启用, false=禁用",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["interface_name", "enable"],
        },
        "parse_commands": None,
    },
    "config_acl_standard": {
        "name": "标准 ACL 配置",
        "description": "配置标准访问控制列表（基于源地址）",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
acl number {{ params.acl_number }}
rule {{ params.rule_id }} {{ params.action }} source {{ params.source_ip }} {{ params.source_wildcard }}
quit
return
{% elif device.vendor == 'huawei' %}
system-view
acl {{ params.acl_number }}
rule {{ params.rule_id }} {{ params.action }} source {{ params.source_ip }} {{ params.source_wildcard }}
quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
access-list {{ params.acl_number }} {{ params.action }} {{ params.source_ip }} {{ params.source_wildcard }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "acl_number": {
                    "type": "integer",
                    "title": "ACL 编号",
                    "description": "标准 ACL 编号（H3C/Huawei: 2000-2999, Cisco: 1-99）",
                    "minimum": 1,
                    "maximum": 2999,
                },
                "rule_id": {
                    "type": "integer",
                    "title": "规则 ID",
                    "description": "规则序号",
                    "minimum": 0,
                    "maximum": 65534,
                },
                "action": {
                    "type": "string",
                    "title": "动作",
                    "enum": ["permit", "deny"],
                },
                "source_ip": {
                    "type": "string",
                    "title": "源 IP",
                    "format": "ipv4",
                    "description": "例如: 192.168.1.0",
                },
                "source_wildcard": {
                    "type": "string",
                    "title": "通配符掩码",
                    "description": "例如: 0.0.0.255",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["acl_number", "rule_id", "action", "source_ip", "source_wildcard"],
        },
        "parse_commands": None,
    },
    "config_acl_extended": {
        "name": "扩展 ACL 配置",
        "description": "配置扩展访问控制列表（基于源/目的地址和端口）",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
acl number {{ params.acl_number }}
rule {{ params.rule_id }} {{ params.action }} {{ params.protocol }} source {{ params.source_ip }} {{ params.source_wildcard }} destination {{ params.dest_ip }} {{ params.dest_wildcard }}{% if params.dest_port %} destination-port eq {{ params.dest_port }}{% endif %}

quit
return
{% elif device.vendor == 'huawei' %}
system-view
acl {{ params.acl_number }}
rule {{ params.rule_id }} {{ params.action }} {{ params.protocol }} source {{ params.source_ip }} {{ params.source_wildcard }} destination {{ params.dest_ip }} {{ params.dest_wildcard }}{% if params.dest_port %} destination-port eq {{ params.dest_port }}{% endif %}

quit
return
{% elif device.vendor == 'cisco' %}
configure terminal
ip access-list extended {{ params.acl_number }}
{{ params.rule_id }} {{ params.action }} {{ params.protocol }} {{ params.source_ip }} {{ params.source_wildcard }} {{ params.dest_ip }} {{ params.dest_wildcard }}{% if params.dest_port %} eq {{ params.dest_port }}{% endif %}

end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "acl_number": {
                    "type": "integer",
                    "title": "ACL 编号",
                    "description": "扩展 ACL 编号（H3C/Huawei: 3000-3999, Cisco: 100-199）",
                    "minimum": 100,
                    "maximum": 3999,
                },
                "rule_id": {
                    "type": "integer",
                    "title": "规则 ID",
                    "minimum": 0,
                    "maximum": 65534,
                },
                "action": {
                    "type": "string",
                    "title": "动作",
                    "enum": ["permit", "deny"],
                },
                "protocol": {
                    "type": "string",
                    "title": "协议",
                    "enum": ["ip", "tcp", "udp", "icmp"],
                },
                "source_ip": {
                    "type": "string",
                    "title": "源 IP",
                    "format": "ipv4",
                },
                "source_wildcard": {
                    "type": "string",
                    "title": "源通配符",
                },
                "dest_ip": {
                    "type": "string",
                    "title": "目的 IP",
                    "format": "ipv4",
                },
                "dest_wildcard": {
                    "type": "string",
                    "title": "目的通配符",
                },
                "dest_port": {
                    "type": "integer",
                    "title": "目的端口",
                    "description": "可选，TCP/UDP 时有效",
                    "minimum": 1,
                    "maximum": 65535,
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["acl_number", "rule_id", "action", "protocol", "source_ip", "source_wildcard", "dest_ip", "dest_wildcard"],
        },
        "parse_commands": None,
    },
    "config_static_route": {
        "name": "静态路由配置",
        "description": "配置静态路由",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
ip route-static {{ params.dest_network }} {{ params.dest_mask }} {{ params.next_hop }}{% if params.preference %} preference {{ params.preference }}{% endif %}

return
{% elif device.vendor == 'huawei' %}
system-view
ip route-static {{ params.dest_network }} {{ params.dest_mask }} {{ params.next_hop }}{% if params.preference %} preference {{ params.preference }}{% endif %}

return
{% elif device.vendor == 'cisco' %}
configure terminal
ip route {{ params.dest_network }} {{ params.dest_mask }} {{ params.next_hop }}{% if params.preference %} {{ params.preference }}{% endif %}

end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "dest_network": {
                    "type": "string",
                    "title": "目的网络",
                    "format": "ipv4",
                    "description": "例如: 10.0.0.0",
                },
                "dest_mask": {
                    "type": "string",
                    "title": "子网掩码",
                    "description": "例如: 255.255.255.0",
                },
                "next_hop": {
                    "type": "string",
                    "title": "下一跳",
                    "format": "ipv4",
                    "description": "下一跳 IP 地址",
                },
                "preference": {
                    "type": "integer",
                    "title": "优先级",
                    "description": "可选，路由优先级",
                    "minimum": 1,
                    "maximum": 255,
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["dest_network", "dest_mask", "next_hop"],
        },
        "parse_commands": None,
    },
    # ===== 新增查看类操作 =====
    "show_acl": {
        "name": "查看 ACL",
        "description": "查看访问控制列表配置",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
{% if params.acl_number %}
display acl {{ params.acl_number }}
{% else %}
display acl all
{% endif %}
{% elif device.vendor == 'huawei' %}
{% if params.acl_number %}
display acl {{ params.acl_number }}
{% else %}
display acl all
{% endif %}
{% elif device.vendor == 'cisco' %}
{% if params.acl_number %}
show access-lists {{ params.acl_number }}
{% else %}
show access-lists
{% endif %}
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "acl_number": {
                    "type": "integer",
                    "title": "ACL 编号",
                    "description": "留空则查看所有 ACL",
                }
            },
            "required": [],
        },
        "parse_commands": {
            "h3c": "display acl all",
            "huawei": "display acl all",
            "cisco": "show access-lists",
        },
    },
    "show_interface_brief": {
        "name": "接口概览",
        "description": "查看所有接口的概要信息",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display interface brief
{% elif device.vendor == 'huawei' %}
display interface brief
{% elif device.vendor == 'cisco' %}
show ip interface brief
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": {
            "h3c": "display interface brief",
            "huawei": "display interface brief",
            "cisco": "show ip interface brief",
        },
    },
    "show_cpu_memory": {
        "name": "CPU/内存使用",
        "description": "查看设备 CPU 和内存使用情况",
        "category": PRESET_CATEGORY_SHOW,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
display cpu-usage
display memory
{% elif device.vendor == 'huawei' %}
display cpu-usage
display memory-usage
{% elif device.vendor == 'cisco' %}
show processes cpu
show memory statistics
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": {
            "h3c": "display cpu-usage",
            "huawei": "display cpu-usage",
            "cisco": "show processes cpu",
        },
    },
    # ===== 新增配置类操作 =====
    "config_save": {
        "name": "保存配置",
        "description": "将当前配置保存到启动配置（持久化）",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": "",  # 空模板，直接调用保存函数
        "parameters_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "parse_commands": None,
        "is_save_only": True,  # 标记为仅保存操作
    },
    "delete_vlan": {
        "name": "删除 VLAN",
        "description": "删除指定的 VLAN",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
undo vlan {{ params.vlan_id }}
return
{% elif device.vendor == 'huawei' %}
system-view
undo vlan {{ params.vlan_id }}
return
{% elif device.vendor == 'cisco' %}
configure terminal
no vlan {{ params.vlan_id }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "vlan_id": {
                    "type": "integer",
                    "title": "VLAN ID",
                    "description": "要删除的 VLAN ID",
                    "minimum": 1,
                    "maximum": 4094,
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["vlan_id"],
        },
        "parse_commands": None,
    },
    "config_ntp": {
        "name": "NTP 配置",
        "description": "配置 NTP 时间同步服务器",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
ntp-service unicast-server {{ params.ntp_server }}
return
{% elif device.vendor == 'huawei' %}
system-view
ntp-service unicast-server {{ params.ntp_server }}
return
{% elif device.vendor == 'cisco' %}
configure terminal
ntp server {{ params.ntp_server }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "ntp_server": {
                    "type": "string",
                    "title": "NTP 服务器",
                    "description": "NTP 服务器 IP 地址或域名",
                    "format": "ipv4",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["ntp_server"],
        },
        "parse_commands": None,
    },
    "config_hostname": {
        "name": "修改主机名",
        "description": "修改设备主机名",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
sysname {{ params.hostname }}
return
{% elif device.vendor == 'huawei' %}
system-view
sysname {{ params.hostname }}
return
{% elif device.vendor == 'cisco' %}
configure terminal
hostname {{ params.hostname }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "title": "主机名",
                    "description": "新的设备主机名",
                    "maxLength": 64,
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["hostname"],
        },
        "parse_commands": None,
    },
    "config_syslog": {
        "name": "Syslog 配置",
        "description": "配置日志服务器（Syslog）",
        "category": PRESET_CATEGORY_CONFIG,
        "supported_vendors": ["h3c", "huawei", "cisco"],
        "template": """{% if device.vendor == 'h3c' %}
system-view
info-center loghost {{ params.server_ip }}
return
{% elif device.vendor == 'huawei' %}
system-view
info-center loghost {{ params.server_ip }}
return
{% elif device.vendor == 'cisco' %}
configure terminal
logging host {{ params.server_ip }}
end
{% endif %}""",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "server_ip": {
                    "type": "string",
                    "title": "日志服务器 IP",
                    "description": "Syslog 服务器 IP 地址",
                    "format": "ipv4",
                },
                "auto_save": {
                    "type": "boolean",
                    "title": "自动保存",
                    "description": "配置完成后是否自动保存到启动配置",
                    "default": False,
                },
            },
            "required": ["server_ip"],
        },
        "parse_commands": None,
    },
}


def get_preset(preset_id: str) -> dict[str, Any] | None:
    """获取预设模板定义。

    Args:
        preset_id: 预设模板 ID

    Returns:
        dict[str, Any] | None: 预设模板定义字典，不存在返回 None
    """
    return PRESET_TEMPLATES.get(preset_id)


def list_presets() -> list[dict[str, Any]]:
    """列出所有预设模板（简要信息）。

    Returns:
        list[dict[str, Any]]: 预设模板列表，每项包含 id、name、description、category、supported_vendors 字段
    """
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
