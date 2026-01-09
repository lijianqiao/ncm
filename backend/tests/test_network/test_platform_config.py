"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_platform_config.py
@DateTime: 2026-01-09 18:40:00
@Docs: 平台配置测试 (Platform Configuration Tests).
"""

import pytest

from app.network.platform_config import (
    COMMAND_MAP,
    NTC_PLATFORM_MAP,
    VENDOR_PLATFORM_MAP,
    detect_vendor_from_banner,
    detect_vendor_from_version,
    get_command,
    get_ntc_platform,
    get_platform_for_vendor,
    get_scrapli_options,
)


class TestVendorPlatformMapping:
    """测试厂商到平台的映射。"""

    def test_h3c_maps_to_hp_comware(self):
        assert get_platform_for_vendor("h3c") == "hp_comware"
        assert get_platform_for_vendor("H3C") == "hp_comware"

    def test_huawei_maps_to_huawei_vrp(self):
        assert get_platform_for_vendor("huawei") == "huawei_vrp"
        assert get_platform_for_vendor("HUAWEI") == "huawei_vrp"

    def test_cisco_maps_to_cisco_iosxe(self):
        assert get_platform_for_vendor("cisco") == "cisco_iosxe"

    def test_unknown_vendor_defaults_to_cisco(self):
        assert get_platform_for_vendor("unknown") == "cisco_iosxe"


class TestNtcPlatformMapping:
    """测试 ntc-templates 平台映射。"""

    def test_hp_comware_mapping(self):
        assert get_ntc_platform("hp_comware") == "hp_comware"

    def test_cisco_iosxe_maps_to_cisco_ios(self):
        assert get_ntc_platform("cisco_iosxe") == "cisco_ios"

    def test_unknown_platform_returns_as_is(self):
        assert get_ntc_platform("unknown_platform") == "unknown_platform"


class TestCommandMapping:
    """测试命令映射。"""

    def test_backup_config_hp_comware(self):
        cmd = get_command("backup_config", "hp_comware")
        assert cmd == "display current-configuration"

    def test_backup_config_cisco(self):
        cmd = get_command("backup_config", "cisco_iosxe")
        assert cmd == "show running-config"

    def test_arp_table_hp_comware(self):
        cmd = get_command("arp_table", "hp_comware")
        assert cmd == "display arp"

    def test_unknown_command_raises_error(self):
        with pytest.raises(ValueError, match="未知的命令类型"):
            get_command("unknown_command", "hp_comware")

    def test_unsupported_platform_uses_cisco_default(self):
        # 未知平台应该 fallback 到 cisco_iosxe
        cmd = get_command("backup_config", "unknown_platform")
        assert cmd == "show running-config"


class TestScrapliOptions:
    """测试 Scrapli 连接参数。"""

    def test_default_options_exist(self):
        options = get_scrapli_options("hp_comware")
        assert "auth_strict_key" in options
        assert "ssh_config_file" in options
        assert "transport" in options

    def test_hp_comware_uses_asyncssh(self):
        options = get_scrapli_options("hp_comware")
        assert options["transport"] == "asyncssh"


class TestVendorDetection:
    """测试厂商自动检测。"""

    def test_detect_h3c_from_banner(self):
        banner = "H3C Comware Platform Software"
        assert detect_vendor_from_banner(banner) == "h3c"

    def test_detect_huawei_from_banner(self):
        banner = "Huawei Versatile Routing Platform Software"
        assert detect_vendor_from_banner(banner) == "huawei"

    def test_detect_cisco_from_banner(self):
        banner = "Cisco IOS Software"
        assert detect_vendor_from_banner(banner) == "cisco"

    def test_unknown_banner_returns_none(self):
        banner = "Unknown Device Banner"
        assert detect_vendor_from_banner(banner) is None

    def test_detect_h3c_from_version(self):
        version_output = """
H3C Comware Platform Software
Comware Software, Version 7.1.075, Release 0427P22
Copyright (c) 2004-2024 New H3C Technologies Co., Ltd.
"""
        assert detect_vendor_from_version(version_output) == "h3c"

    def test_detect_cisco_from_version(self):
        version_output = """
Cisco IOS XE Software, Version 17.03.04a
Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software
"""
        assert detect_vendor_from_version(version_output) == "cisco"
