"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: async_tasks.py
@DateTime: 2026-01-14 00:30:00
@Docs: Scrapli 异步任务函数库。

提供通用的异步网络设备操作任务，配合 AsyncRunner 使用。
所有函数都是独立的异步函数，接收 Host 对象并返回执行结果。
"""

from typing import TYPE_CHECKING, Any

from scrapli import AsyncScrapli
from scrapli.response import Response

from app.core.config import settings
from app.core.logger import logger
from app.network.platform_config import get_scrapli_options

if TYPE_CHECKING:
    from nornir.core.inventory import Host


def _get_scrapli_kwargs(host: "Host") -> dict[str, Any]:
    """
    从 Nornir Host 对象提取 Scrapli 连接参数。

    使用 platform_config.py 中的统一配置作为基础，
    然后覆盖主机特定的连接信息和超时参数。

    Args:
        host: Nornir Host 对象

    Returns:
        Scrapli 连接参数字典
    """
    from app.network.platform_config import get_platform_for_vendor

    raw_platform = host.platform or "hp_comware"

    # 如果 platform 是厂商名（如 h3c, huawei），转换为 Scrapli 平台名
    # get_platform_for_vendor 会处理映射，如果已经是 Scrapli 平台名则直接返回
    try:
        platform = get_platform_for_vendor(raw_platform)
    except ValueError:
        # 如果无法识别，假设它已经是有效的 Scrapli 平台名
        platform = raw_platform

    # 从 platform_config.py 获取平台特定的 Scrapli 配置
    base_options = get_scrapli_options(platform)

    # 从 host 的 connection_options 中获取额外配置（优先级更高）
    extras = {}
    if host.connection_options and "scrapli" in host.connection_options:
        extras = host.connection_options["scrapli"].extras or {}

    # 合并配置：base_options → extras → 固定覆盖项
    result = {
        **base_options,
        **extras,
        # 主机特定信息（必须覆盖）
        "host": host.hostname,
        "auth_username": host.username,
        "auth_password": host.password,
        "port": host.port or 22,
        "platform": platform,
        # 使用配置文件中的超时参数
        "timeout_socket": settings.ASYNC_SSH_CONNECT_TIMEOUT,
        "timeout_transport": settings.ASYNC_SSH_CONNECT_TIMEOUT,
        "timeout_ops": settings.ASYNC_SSH_TIMEOUT,
    }

    return result


async def async_send_command(host: "Host", command: str) -> dict[str, Any]:
    """
    异步执行单条命令。

    Args:
        host: Nornir Host 对象
        command: 要执行的命令

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 命令输出
        - elapsed_time: 执行耗时
        - failed: 是否失败
    """
    kwargs = _get_scrapli_kwargs(host)
    device_name = host.data.get("device_name", host.name)

    try:
        async with AsyncScrapli(**kwargs) as conn:
            response: Response = await conn.send_command(command)
            return {
                "success": not response.failed,
                "result": response.result,
                "elapsed_time": response.elapsed_time,
                "failed": response.failed,
            }
    except TimeoutError:
        logger.warning("命令执行超时", host=device_name, command=command)
        raise
    except Exception as e:
        logger.error("命令执行失败", host=device_name, command=command, error=str(e), exc_info=True)
        raise


async def async_send_commands(host: "Host", commands: list[str]) -> dict[str, Any]:
    """
    异步执行多条命令。

    Args:
        host: Nornir Host 对象
        commands: 命令列表

    Returns:
        包含执行结果的字典：
        - success: 是否全部成功
        - results: 各命令输出列表
        - failed_commands: 失败的命令列表
    """
    kwargs = _get_scrapli_kwargs(host)
    device_name = host.data.get("device_name", host.name)

    try:
        async with AsyncScrapli(**kwargs) as conn:
            responses = await conn.send_commands(commands)

            results = []
            failed_commands = []
            for cmd, resp in zip(commands, responses, strict=False):
                results.append(
                    {
                        "command": cmd,
                        "result": resp.result,
                        "failed": resp.failed,
                    }
                )
                if resp.failed:
                    failed_commands.append(cmd)

            return {
                "success": len(failed_commands) == 0,
                "results": results,
                "failed_commands": failed_commands,
            }
    except Exception as e:
        logger.error("批量命令执行失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_send_config(host: "Host", config: str | list[str]) -> dict[str, Any]:
    """
    异步下发配置。

    Args:
        host: Nornir Host 对象
        config: 配置内容（字符串或行列表）

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 配置下发输出
    """
    kwargs = _get_scrapli_kwargs(host)
    device_name = host.data.get("device_name", host.name)

    # 配置转为行列表
    if isinstance(config, str):
        config_lines = [line.strip() for line in config.splitlines() if line.strip()]
    else:
        config_lines = config

    try:
        async with AsyncScrapli(**kwargs) as conn:
            response = await conn.send_configs(config_lines)

            # 检查是否有失败的配置行
            failed_lines = [r for r in response if r.failed]

            return {
                "success": len(failed_lines) == 0,
                "result": "\n".join(r.result for r in response),
                "failed_count": len(failed_lines),
            }
    except Exception as e:
        logger.error("配置下发失败", host=device_name, error=str(e), exc_info=True)
        raise


async def async_get_prompt(host: "Host") -> dict[str, Any]:
    """
    异步获取设备提示符（用于连通性测试）。

    Args:
        host: Nornir Host 对象

    Returns:
        包含提示符的字典：
        - success: 是否成功
        - prompt: 设备提示符
    """
    kwargs = _get_scrapli_kwargs(host)

    try:
        async with AsyncScrapli(**kwargs) as conn:
            prompt = await conn.get_prompt()
            return {
                "success": True,
                "prompt": prompt,
            }
    except Exception as e:
        logger.error("获取提示符失败", host=host.name, error=str(e), exc_info=True)
        raise


async def async_collect_config(host: "Host") -> dict[str, Any]:
    """
    异步采集设备运行配置。

    根据设备平台自动选择正确的命令。

    Args:
        host: Nornir Host 对象

    Returns:
        包含配置内容的字典：
        - success: 是否成功
        - config: 配置内容
        - platform: 设备平台
    """
    from app.network.platform_config import get_command, get_platform_for_vendor

    raw_platform = host.platform or "hp_comware"

    # 如果 platform 是厂商名（如 h3c, huawei），转换为 Scrapli 平台名
    try:
        platform = get_platform_for_vendor(raw_platform)
    except ValueError:
        platform = raw_platform

    # 使用统一的命令映射
    try:
        command = get_command("backup_config", platform)
    except ValueError:
        command = "show running-config"

    result = await async_send_command(host, command)
    return {
        "success": result["success"],
        "config": result["result"],
        "platform": platform,
    }


async def async_deploy_from_host_data(host: "Host") -> dict[str, Any]:
    """
    异步下发配置（从 host.data['deploy_configs'] 读取）。

    用于批量下发场景，每台设备的配置内容存储在 host.data 中。

    Args:
        host: Nornir Host 对象，data 中需包含 'deploy_configs' 键

    Returns:
        包含执行结果的字典：
        - success: 是否成功
        - result: 下发输出
        - device_id: 设备 ID
    """
    device_id = host.data.get("device_id", host.name)
    device_name = host.data.get("device_name", host.name)
    configs: list[str] = host.data.get("deploy_configs", [])  # type: ignore[assignment]

    if not configs:
        return {
            "success": True,
            "result": "无配置需要下发",
            "device_id": device_id,
            "skipped": True,
        }

    try:
        result = await async_send_config(host, configs)
        return {
            "success": result["success"],
            "result": result["result"],
            "device_id": device_id,
            "failed_count": result.get("failed_count", 0),
        }
    except Exception as e:
        logger.error("异步配置下发失败", host=device_name, device_id=device_id, error=str(e), exc_info=True)
        raise
