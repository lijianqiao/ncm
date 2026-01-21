"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: nornir_config.py
@DateTime: 2026-01-09 12:45:00
@Docs: Nornir 框架配置模块 (Nornir Framework Configuration).

Nornir 是专为网络自动化设计的框架，提供：
- 设备清单管理 (Inventory)
- 并发任务执行
- 失败容错与结果聚合
- 插件化架构 (支持 Scrapli/Netmiko/NAPALM)
"""

import importlib
from typing import Any

from nornir.core import Nornir
from nornir.core.exceptions import PluginAlreadyRegistered
from nornir.core.inventory import ConnectionOptions, Defaults, Group, Groups, Host, Hosts, Inventory, ParentGroups
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.plugins.runners import ThreadedRunner

from app.core.config import settings
from app.core.logger import logger


def _ensure_scrapli_plugin_registered() -> None:
    """确保 nornir_scrapli 的 scrapli connection plugin 已注册。

    注意：我们在 init_nornir 中绕过 InitNornir 直接构造 Nornir，
    这会跳过一些插件加载逻辑，因此需要在运行任务前显式注册。
    """

    # 显式导入并注册 scrapli connection plugin
    # 注意：nornir_scrapli.connection.Scrapli 是 scrapli 驱动类（需要 platform/host 参数），
    # 真正的 Nornir 连接插件是 ScrapliCore（无参构造，open/close 由 Nornir 调用）。
    module = importlib.import_module("nornir_scrapli.connection")
    plugin_cls = getattr(module, "ScrapliCore", None)
    if plugin_cls is None:
        raise RuntimeError("nornir_scrapli.connection 中未找到 ScrapliCore 连接插件")

    existing = ConnectionPluginRegister.available.get("scrapli")
    if existing == plugin_cls:
        return

    try:
        ConnectionPluginRegister.register("scrapli", plugin_cls)
    except PluginAlreadyRegistered:
        # 若之前错误注册了 Scrapli（驱动类）等，强制覆盖为 ScrapliCore
        ConnectionPluginRegister.available["scrapli"] = plugin_cls


def create_nornir_inventory(
    hosts_data: list[dict[str, Any]],
    groups_data: list[dict[str, Any]] | None = None,
) -> Inventory:
    """
    根据传入的设备数据动态创建 Nornir Inventory。

    Args:
        hosts_data: 主机数据列表，每个字典包含以下字段：
            - name: 设备名称 (唯一标识)
            - hostname: IP 地址或主机名
            - platform: 设备平台 (cisco_iosxe, huawei, h3c, etc.)
            - username: 登录用户名 (可选，从默认值继承)
            - password: 登录密码 (可选，从默认值继承)
            - port: SSH 端口 (可选，默认 22)
            - groups: 所属分组列表 (可选)
            - data: 额外数据字典 (可选)
        groups_data: 分组数据列表 (可选)

    Returns:
        Inventory: Nornir Inventory 实例
    """
    hosts = Hosts()
    groups = Groups()

    # 创建默认分组
    default_groups = {
        "core": Group(name="core", data={"role": "core", "priority": 1}),
        "distribution": Group(name="distribution", data={"role": "distribution", "priority": 2}),
        "access": Group(name="access", data={"role": "access", "priority": 3}),
        "cisco": Group(
            name="cisco",
            platform="cisco_iosxe",
            connection_options={
                "scrapli": ConnectionOptions(
                    extras={"auth_strict_key": False, "ssh_config_file": "", "transport": "ssh2"}
                )
            },
        ),
        "huawei": Group(
            name="huawei",
            platform="huawei_vrp",
            connection_options={
                "scrapli": ConnectionOptions(
                    extras={"auth_strict_key": False, "ssh_config_file": "", "transport": "ssh2"}
                )
            },
        ),
        "h3c": Group(
            name="h3c",
            platform="hp_comware",
            connection_options={
                "scrapli": ConnectionOptions(
                    extras={"auth_strict_key": False, "ssh_config_file": "", "transport": "ssh2"}
                )
            },
        ),
    }
    groups.update(default_groups)

    # 添加自定义分组
    if groups_data:
        for group_info in groups_data:
            group_name = group_info.get("name")
            if group_name and group_name not in groups:
                groups[group_name] = Group(
                    name=group_name,
                    platform=group_info.get("platform"),
                    data=group_info.get("data", {}),
                )

    # 创建主机
    for host_info in hosts_data:
        host_name = host_info.get("name")
        if not host_name:
            logger.warning("跳过缺少 name 字段的主机", host_info=host_info)
            continue

        platform = host_info.get("platform")
        scrapli_extras: dict[str, Any] = {
            "auth_strict_key": False,
            "ssh_config_file": "",
            "transport": "ssh2",
            # 认证超时设置（秒）- 加快 OTP 失败检测
            "timeout_socket": 10,  # Socket 连接超时
            "timeout_transport": 15,  # Transport 层超时（含认证）
        }

        host_groups = []
        for g in host_info.get("groups", []):
            if g in groups:
                host_groups.append(groups[g])

        hosts[host_name] = Host(
            name=host_name,
            hostname=host_info.get("hostname", host_name),
            platform=platform,
            username=host_info.get("username"),
            password=host_info.get("password"),
            port=host_info.get("port", 22),
            groups=ParentGroups(host_groups),
            data=host_info.get("data", {}),
            connection_options={"scrapli": ConnectionOptions(extras=scrapli_extras)},
        )

    # 创建默认配置
    defaults = Defaults(
        username=settings.FIRST_SUPERUSER,  # 后续替换为设备凭据
        password=settings.FIRST_SUPERUSER_PASSWORD,  # 后续替换为设备凭据
        connection_options={
            "scrapli": ConnectionOptions(
                extras={
                    "auth_strict_key": False,
                    "ssh_config_file": "",
                    "transport": "ssh2",
                }
            )
        },
    )

    return Inventory(hosts=hosts, groups=groups, defaults=defaults)


def init_nornir(
    hosts_data: list[dict[str, Any]],
    groups_data: list[dict[str, Any]] | None = None,
    num_workers: int = 50,
) -> Nornir:
    """
    初始化 Nornir 实例（动态 Inventory）。

    Args:
        hosts_data: 主机数据列表
        groups_data: 分组数据列表 (可选)
        num_workers: 并发 Worker 数量 (默认 50)

    Returns:
        Nornir: 初始化完成的 Nornir 实例
    """
    _ensure_scrapli_plugin_registered()
    inventory = create_nornir_inventory(hosts_data, groups_data)

    # nornir.InitNornir() 会走 Config.from_dict()，要求 inventory 为 dict 配置。
    # 这里我们是动态构造 Inventory 实例，因此直接构造 Nornir。
    nr = Nornir(
        inventory=inventory,
        runner=ThreadedRunner(num_workers=num_workers),
    )

    logger.info(
        "Nornir 初始化完成",
        hosts_count=len(nr.inventory.hosts),
        groups_count=len(nr.inventory.groups),
        num_workers=num_workers,
    )

    return nr


def init_nornir_from_db(
    devices: list[Any],
    num_workers: int = 50,
) -> Nornir:
    """
    从数据库 Device 模型列表初始化 Nornir。

    Args:
        devices: Device 模型实例列表
        num_workers: 并发 Worker 数量

    Returns:
        Nornir: 初始化完成的 Nornir 实例
    """
    hosts_data = []

    for device in devices:
        host_info = {
            "name": str(device.id),  # 使用设备 ID 作为唯一标识
            "hostname": device.ip_address,
            "platform": device.platform,  # cisco_iosxe, huawei_vrp, hp_comware
            "username": device.username,
            "password": device.password,  # 需要解密后传入
            "port": device.ssh_port or 22,
            "groups": [device.device_group] if device.device_group else [],
            "data": {
                "device_id": str(device.id),
                "device_name": device.name,
                "vendor": device.vendor,
                "model": device.model,
                "location": device.location,
            },
        }
        hosts_data.append(host_info)

    return init_nornir(hosts_data, num_workers=num_workers)


def init_nornir_async(
    hosts_data: list[dict[str, Any]],
    groups_data: list[dict[str, Any]] | None = None,
    num_workers: int | None = None,
) -> Inventory:
    """
    初始化异步模式的 Nornir Inventory。

    注意：返回 Inventory 而非 Nornir 对象，因为 AsyncRunner 不兼容 Nornir RunnerPlugin 协议。
    应配合 run_async_tasks() 或 run_async_tasks_sync() 使用。

    Args:
        hosts_data: 主机数据列表
        groups_data: 分组数据列表 (可选)
        num_workers: 未使用，保留以兼容 API

    Returns:
        Inventory: Nornir Inventory 实例

    Example:
        ```python
        from app.network.nornir_config import init_nornir_async
        from app.network.async_runner import run_async_tasks_sync
        from app.network.async_tasks import async_send_command

        inventory = init_nornir_async(hosts_data)
        results = run_async_tasks_sync(
            inventory.hosts,
            async_send_command,
            command=\"display version\",
        )
        ```
    """
    # 复用统一的 Inventory 创建函数
    inventory = create_nornir_inventory(hosts_data, groups_data)

    logger.info(
        "Nornir 异步 Inventory 创建完成",
        hosts_count=len(inventory.hosts),
        groups_count=len(inventory.groups),
    )

    return inventory


def init_nornir_async_from_db(
    devices: list[Any],
    num_workers: int | None = None,
) -> Inventory:
    """
    从数据库 Device 模型列表初始化异步 Nornir Inventory。

    Args:
        devices: Device 模型实例列表
        num_workers: 未使用，保留以兼容 API

    Returns:
        Inventory: Nornir Inventory 实例
    """
    hosts_data = []

    for device in devices:
        host_info = {
            "name": str(device.id),
            "hostname": device.ip_address,
            "platform": device.platform,
            "username": device.username,
            "password": device.password,
            "port": device.ssh_port or 22,
            "groups": [device.device_group] if device.device_group else [],
            "data": {
                "device_id": str(device.id),
                "device_name": device.name,
                "vendor": device.vendor,
                "model": device.model,
                "location": device.location,
            },
        }
        hosts_data.append(host_info)

    return init_nornir_async(hosts_data, num_workers=num_workers)
