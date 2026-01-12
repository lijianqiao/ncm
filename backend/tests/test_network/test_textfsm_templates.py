"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_textfsm_templates.py
@DateTime: 2026-01-09 18:30:00
@Docs: TextFSM 模板测试 (TextFSM Template Tests).

验证 ntc-templates 和自定义模板的解析功能。
"""

from app.network.textfsm_parser import (
    parse_arp_table,
    parse_command_output,
    parse_interface_status,
    parse_lldp_neighbors,
    parse_mac_table,
    parse_version,
)


class TestHPComwareNtcTemplates:
    """测试 HP Comware (H3C) ntc-templates 模板。"""

    def test_parse_display_arp(self):
        """测试 display arp 解析。"""
        output = """
  Type: S-Static   D-Dynamic   O-Openflow   R-Rule   M-Multiport  I-Invalid
IP address       MAC address    VLAN     Interface                Aging Type
10.1.1.1         0001-0001-0001 1        GE1/0/1                   20    D
10.1.1.2         0001-0001-0002 1        GE1/0/2                   18    D
192.168.1.1      0002-0002-0001 10       GE1/0/10                  15    S
"""
        result = parse_arp_table("hp_comware", output)

        assert len(result) == 3
        assert result[0]["ip_address"] == "10.1.1.1"
        assert result[0]["mac_address"] == "0001-0001-0001"
        assert result[0]["vlan_id"] == "1"
        assert result[0]["interface"] == "GE1/0/1"

    def test_parse_display_mac_address(self):
        """测试 display mac-address 解析。"""
        output = """
MAC ADDR         VLAN ID   STATE          PORT INDEX                 AGING
0001-0001-0001   1         Learned        GigabitEthernet1/0/1       AGING
0001-0001-0002   1         Learned        GigabitEthernet1/0/2       AGING
0002-0002-0001   10        Config         GigabitEthernet1/0/10      NOAGED
"""
        result = parse_mac_table("hp_comware", output)

        assert len(result) == 3
        assert result[0]["mac_address"] == "0001-0001-0001"
        assert result[0]["vlan_id"] == "1"
        assert result[0]["state"] == "Learned"
        assert result[0]["interface"] == "GigabitEthernet1/0/1"

    def test_parse_display_interface_brief(self):
        """测试 display interface brief 解析。"""
        output = """
Brief information on interface(s) under route mode:
Link: ADM - administratively down; Stby - standby
Protocol: (s) - spoofing
Interface            Link Protocol Primary IP       Description
GE1/0/1              UP   UP       --               To-Dist1
GE1/0/2              UP   UP       --               To-Dist2
Vlan1                UP   UP       192.168.1.1      Management
"""
        result = parse_interface_status("hp_comware", output)

        assert len(result) == 3
        assert result[0]["interface"] == "GE1/0/1"
        assert result[0]["link"] == "UP"
        assert result[0]["protocol"] == "UP"


class TestHPComwareCustomTemplates:
    """测试 HP Comware (H3C) 自定义模板。"""

    def test_parse_display_version(self):
        """测试 display version 解析（自定义模板）。"""
        output = """
H3C Comware Platform Software
Comware Software, Version 7.1.075, Release 0427P22
Copyright (c) 2004-2024 New H3C Technologies Co., Ltd. All rights reserved.
H3C S5560X-54C-EI uptime is 0 weeks, 2 days, 3 hours, 45 minutes
Last reboot reason : User reboot

Boot image: flash:/s5560x_ei-cmw710-boot-r0427p22.bin
Boot image version: 7.1.075, Release 0427P22
  Compiled Jan 15 2024 16:00:00
System image: flash:/s5560x_ei-cmw710-system-r0427p22.bin
System image version: 7.1.075, Release 0427P22
  Compiled Jan 15 2024 16:30:00
"""
        result = parse_version("hp_comware", output)

        # 自定义模板应该能解析出版本信息
        assert len(result) >= 1
        record = result[0]
        assert record.get("version") == "7.1.075"
        assert record.get("release") == "0427P22"

    def test_parse_display_lldp_neighbors(self):
        """测试 display lldp neighbor-information list 解析（自定义模板）。"""
        output = """
Local Intf             Neighbor Dev         Neighbor Intf                Hold Time
GE1/0/1                H3C-Dist1            GigabitEthernet1/0/24        120
GE1/0/2                H3C-Dist2            GigabitEthernet1/0/24        120
GE1/0/3                H3C-Access1          GigabitEthernet0/0/1         90
"""
        result = parse_lldp_neighbors("hp_comware", output)

        # 自定义模板应该能解析出 LLDP 邻居
        assert len(result) == 3
        assert result[0]["local_interface"] == "GE1/0/1"
        assert result[0]["neighbor_device"] == "H3C-Dist1"
        assert result[0]["neighbor_interface"] == "GigabitEthernet1/0/24"
        assert result[0]["hold_time"] == "120"


class TestCiscoTemplates:
    """测试 Cisco ntc-templates 模板。"""

    def test_parse_show_ip_arp(self):
        """测试 show ip arp 解析。"""
        output = """
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  10.1.1.1               10   0001.0001.0001  ARPA   GigabitEthernet0/0
Internet  10.1.1.2                5   0001.0001.0002  ARPA   GigabitEthernet0/1
"""
        result = parse_arp_table("cisco_ios", output)

        assert len(result) == 2
        assert result[0]["ip_address"] == "10.1.1.1"
        assert result[0]["mac_address"] == "0001.0001.0001"

    def test_parse_show_mac_address_table(self):
        """测试 show mac address-table 解析。"""
        output = """
          Mac Address Table
-------------------------------------------

Vlan    Mac Address       Type        Ports
----    -----------       --------    -----
   1    0001.0001.0001    DYNAMIC     Gi0/1
   1    0001.0001.0002    DYNAMIC     Gi0/2
  10    0002.0002.0001    STATIC      Gi0/10
"""
        result = parse_mac_table("cisco_ios", output)

        assert len(result) == 3
        assert result[0]["destination_address"] == "0001.0001.0001"
        assert result[0]["vlan_id"] == "1"


class TestPlatformMapping:
    """测试平台名称映射。"""

    def test_cisco_iosxe_maps_to_cisco_ios(self):
        """测试 cisco_iosxe 映射到 cisco_ios。"""
        output = """
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  10.1.1.1               10   0001.0001.0001  ARPA   GigabitEthernet0/0
"""
        # cisco_iosxe 应该能正确解析（内部映射到 cisco_ios）
        result = parse_command_output("cisco_iosxe", "show ip arp", output)
        assert len(result) == 1

    def test_unsupported_platform_returns_empty(self):
        """测试不支持的平台返回空列表而非异常。"""
        result = parse_command_output("unknown_platform", "some command", "some output")
        assert result == []

    def test_unsupported_command_returns_empty(self):
        """测试不支持的命令返回空列表而非异常。"""
        result = parse_command_output("hp_comware", "display unknown-command", "some output")
        assert result == []


class TestCustomTemplateLoader:
    """测试自定义模板加载器。"""

    def test_custom_template_exists(self):
        """测试自定义模板文件存在。"""
        from app.network.templates import CUSTOM_TEMPLATES, get_template_path

        # 验证注册的模板
        assert "hp_comware_display_version" in CUSTOM_TEMPLATES
        assert "hp_comware_display_lldp_neighbor-information_list" in CUSTOM_TEMPLATES

        # 验证路径存在
        version_path = get_template_path("hp_comware", "display version")
        assert version_path is not None

        lldp_path = get_template_path("hp_comware", "display lldp neighbor-information list")
        assert lldp_path is not None

    def test_nonexistent_template_returns_none(self):
        """测试不存在的模板返回 None。"""
        from app.network.templates import get_template_path

        result = get_template_path("hp_comware", "display nonexistent")
        assert result is None
