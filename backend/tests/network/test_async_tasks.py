"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_async_tasks.py
@DateTime: 2026-01-14 01:00:00
@Docs: 异步任务测试脚本。

用于验证 AsyncRunner + Scrapli Async 的异步网络任务执行能力。
"""

import asyncio
import time
from typing import Any


# 测试用的模拟 Host 对象
class MockHost:
    """模拟 Nornir Host 对象用于测试。"""

    def __init__(
        self,
        name: str,
        hostname: str,
        platform: str = "hp_comware",
        username: str = "admin",
        password: str = "admin",
        port: int = 22,
        data: dict[str, Any] | None = None,
    ):
        self.name = name
        self.hostname = hostname
        self.platform = platform
        self.username = username
        self.password = password
        self.port = port
        self.data = data or {}
        self.connection_options = {}


async def test_async_send_command():
    """测试异步命令执行（需要真实设备）。"""
    from app.network.async_tasks import async_send_command

    # 创建测试 Host（请替换为真实设备信息）
    host = MockHost(
        name="test-device",
        hostname="192.168.1.1",  # 替换为真实 IP
        platform="hp_comware",
        username="admin",  # 替换为真实用户名
        password="admin123",  # 替换为真实密码
    )

    print(f"测试设备: {host.hostname}")
    print("执行命令: display version")

    start = time.time()
    try:
        result = await async_send_command(host, "display version")
        elapsed = time.time() - start

        print(f"执行结果: {'成功' if result['success'] else '失败'}")
        print(f"耗时: {elapsed:.2f}s")
        if result.get("result"):
            print(f"输出预览: {result['result'][:200]}...")
        return result
    except Exception as e:
        print(f"执行失败: {e}")
        raise


async def test_async_runner_batch():
    """测试 AsyncRunner 批量执行（模拟多设备）。"""
    from app.network.async_runner import run_async_tasks
    from app.network.async_tasks import async_get_prompt

    # 创建多个模拟 Host（请替换为真实设备信息）
    hosts = {
        "device-1": MockHost("device-1", "192.168.1.1", password="admin123"),
        "device-2": MockHost("device-2", "192.168.1.2", password="admin123"),
        "device-3": MockHost("device-3", "192.168.1.3", password="admin123"),
    }

    print(f"测试 {len(hosts)} 台设备批量连接测试...")

    start = time.time()
    try:
        results = await run_async_tasks(
            hosts,  # type: ignore
            async_get_prompt,
            num_workers=10,
        )
        elapsed = time.time() - start

        success_count = sum(1 for r in results.values() if not r.failed)
        failed_count = len(results) - success_count

        print("批量执行完成:")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        print(f"  总耗时: {elapsed:.2f}s")
        print(f"  平均耗时: {elapsed / len(hosts):.2f}s/设备")

        return results
    except Exception as e:
        print(f"批量执行失败: {e}")
        raise


async def test_async_collect_config():
    """测试异步配置采集。"""
    from app.network.async_tasks import async_collect_config

    host = MockHost(
        name="test-device",
        hostname="192.168.1.1",  # 替换为真实 IP
        platform="hp_comware",
        username="admin",
        password="admin123",
    )

    print(f"采集设备配置: {host.hostname}")

    start = time.time()
    try:
        result = await async_collect_config(host)
        elapsed = time.time() - start

        print(f"采集结果: {'成功' if result['success'] else '失败'}")
        print(f"耗时: {elapsed:.2f}s")
        if result.get("config"):
            config_lines = result["config"].splitlines()
            print(f"配置行数: {len(config_lines)}")
            print(f"配置大小: {len(result['config'])} bytes")
        return result
    except Exception as e:
        print(f"采集失败: {e}")
        raise


def run_test(test_name: str):
    """运行指定的测试。"""
    tests = {
        "command": test_async_send_command,
        "batch": test_async_runner_batch,
        "config": test_async_collect_config,
    }

    if test_name not in tests:
        print(f"未知测试: {test_name}")
        print(f"可用测试: {', '.join(tests.keys())}")
        return

    print(f"\n{'=' * 50}")
    print(f"运行测试: {test_name}")
    print(f"{'=' * 50}\n")

    asyncio.run(tests[test_name]())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python test_async_tasks.py <test_name>")
        print("可用测试: command, batch, config")
        print("\n示例:")
        print("  python test_async_tasks.py command  # 测试单命令执行")
        print("  python test_async_tasks.py batch    # 测试批量执行")
        print("  python test_async_tasks.py config   # 测试配置采集")
    else:
        run_test(sys.argv[1])
