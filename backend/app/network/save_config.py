"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: save_config.py
@DateTime: 2026-01-22 12:00:00
@Docs: 设备配置保存功能（独立连接）。
"""

import asyncio
import time
from typing import Any

from scrapli import Scrapli
from scrapli.exceptions import (
    ScrapliAuthenticationFailed,
    ScrapliConnectionError,
    ScrapliConnectionNotOpened,
    ScrapliTimeout,
)

from app.core.logger import logger
from app.network.scrapli_utils import build_scrapli_config, disable_paging, save_device_config


async def save_device_config_standalone(
    host: str,
    username: str,
    password: str,
    vendor: str,
    *,
    platform: str = "hp_comware",
    port: int = 22,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    独立建立连接并保存设备配置。

    用于 config_save 预设，无需执行其他配置命令，直接保存当前配置。

    Args:
        host: 设备 IP 地址或主机名
        username: SSH 用户名
        password: SSH 密码
        vendor: 设备厂商 (h3c, huawei, cisco)
        platform: Scrapli 平台
        port: SSH 端口
        timeout: 操作超时时间（秒）

    Returns:
        dict: {"success": bool, "output": str, "error": str | None}
    """
    device_config = build_scrapli_config(
        host=host,
        username=username,
        password=password,
        platform=platform,
        port=port,
        timeout_transport=timeout,
        timeout_ops=timeout,
    )

    start = time.monotonic()
    stage = "init"
    logger.info(
        "开始独立保存配置",
        host=host,
        vendor=vendor,
        platform=platform,
        port=port,
    )

    def _sync_save() -> dict[str, Any]:
        nonlocal stage
        conn = Scrapli(**device_config)
        try:
            stage = "open"
            logger.info("Scrapli 打开连接（保存配置）", host=host, platform=platform)
            conn.open()
            logger.info(
                "Scrapli 连接已打开",
                host=host,
                platform=platform,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

            stage = "prompt"
            prompt = conn.get_prompt()
            logger.info("Scrapli 获取提示符", host=host, platform=platform, prompt=prompt)

            stage = "disable_paging"
            disable_paging(conn, platform)

            stage = "save_config"
            logger.info("开始执行保存配置命令", host=host, vendor=vendor)
            save_result = save_device_config(conn, vendor, timeout_ops=timeout)

            if save_result.get("success"):
                logger.info(
                    "配置保存成功",
                    host=host,
                    vendor=vendor,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            else:
                logger.warning(
                    "配置保存失败",
                    host=host,
                    vendor=vendor,
                    error=save_result.get("error"),
                )

            return save_result

        except ScrapliAuthenticationFailed as e:
            logger.warning("设备认证失败（保存配置）", host=host, platform=platform, error=str(e))
            raise
        except ScrapliTimeout as e:
            logger.warning(
                "设备执行超时（保存配置）",
                host=host,
                platform=platform,
                stage=stage,
                timeout=timeout,
                error=str(e),
            )
            return {"success": False, "output": "", "error": f"保存配置超时: {e}"}
        except ScrapliConnectionNotOpened as e:
            logger.warning("设备连接未打开（保存配置）", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接未打开: {e}"}
        except ScrapliConnectionError as e:
            logger.warning("设备连接错误（保存配置）", host=host, platform=platform, error=str(e))
            return {"success": False, "output": "", "error": f"连接错误: {e}"}
        except Exception as e:
            logger.error("保存配置异常", host=host, platform=platform, error=str(e), exc_info=True)
            return {"success": False, "output": "", "error": str(e)}
        finally:
            try:
                stage = "close"
                conn.close()
                logger.info(
                    "Scrapli 连接已关闭（保存配置）",
                    host=host,
                    platform=platform,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception:
                pass

    return await asyncio.to_thread(_sync_save)
