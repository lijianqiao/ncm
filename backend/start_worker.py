"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: start_worker.py
@DateTime: 2026-01-09 11:55:00
@Docs: Celery Worker/Beat/Flower 启动脚本.

使用方式:
    # 启动默认 Worker (处理所有队列)
    uv run start_worker.py

    # 启动指定队列的 Worker
    uv run start_worker.py --queues deploy,backup,discovery

    # 启动并指定并发数
    uv run start_worker.py --concurrency 8

    # 启动 Worker + Beat（内嵌定时任务调度）
    uv run start_worker.py --beat

    # 启动 Worker + Flower（Worker 同时带监控面板）
    uv run start_worker.py --with-flower

    # 启动 Worker + Beat + Flower（全功能模式）
    uv run start_worker.py --beat --with-flower

    # 单独启动 Beat 调度器（用于分布式部署）
    uv run start_worker.py --beat-only

    # 单独启动 Flower 监控面板（需要另一终端运行 Worker）
    uv run start_worker.py --flower

    # 启动 Flower（带 HTTP Basic Auth）
    uv run start_worker.py --flower --flower-auth admin:password
"""

import argparse
import subprocess
import sys
import threading
import time


def _build_flower_cmd(port: int, basic_auth: str | None = None) -> list[str]:
    """构建 Flower 启动命令。"""
    flower_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery.app:celery_app",
        "flower",
        f"--port={port}",
    ]
    if basic_auth:
        flower_cmd.append(f"--basic-auth={basic_auth}")
    return flower_cmd


def start_flower_background(port: int, basic_auth: str | None = None) -> subprocess.Popen:
    """
    后台启动 Flower 监控面板（非阻塞）。

    Args:
        port: Flower Web UI 端口
        basic_auth: HTTP Basic Auth 认证

    Returns:
        Popen: Flower 子进程对象
    """
    flower_cmd = _build_flower_cmd(port, basic_auth)
    print(f"后台启动 Flower 监控面板: http://localhost:{port}")
    # 使用 Popen 非阻塞启动
    return subprocess.Popen(
        flower_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_flower(port: int, basic_auth: str | None = None) -> int:
    """
    启动 Flower 监控面板（阻塞模式，单独运行）。

    Args:
        port: Flower Web UI 端口
        basic_auth: HTTP Basic Auth 认证，格式 "user:password"

    Returns:
        int: 进程退出码
    """
    flower_cmd = _build_flower_cmd(port, basic_auth)
    print(f"启动 Flower 监控面板: http://localhost:{port}")
    print(f"命令: {' '.join(flower_cmd)}")
    print("\n⚠️  注意：Flower 只是监控面板，需要另一个终端运行 Worker 才能正常工作！")
    print("    另开终端执行: uv run start_worker.py\n")
    return subprocess.call(flower_cmd)


def start_beat_only() -> int:
    """
    单独启动 Celery Beat 调度器。

    用于分布式部署场景，Beat 进程独立运行。

    Returns:
        int: 进程退出码
    """
    beat_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery.app:celery_app",
        "beat",
        "--loglevel=INFO",
    ]

    print("启动 Celery Beat 调度器")
    print(f"命令: {' '.join(beat_cmd)}")
    return subprocess.call(beat_cmd)


def start_worker(
    queues: str,
    concurrency: int,
    loglevel: str,
    pool: str,
    with_beat: bool = False,
    with_flower: bool = False,
    flower_port: int = 5555,
    flower_auth: str | None = None,
) -> int:
    """
    启动 Celery Worker。

    Args:
        queues: 要处理的队列列表，逗号分隔
        concurrency: Worker 并发数
        loglevel: 日志级别
        pool: Worker Pool 类型
        with_beat: 是否同时启动 Beat 调度器
        with_flower: 是否同时启动 Flower 监控面板
        flower_port: Flower 端口
        flower_auth: Flower HTTP Basic Auth

    Returns:
        int: 进程退出码
    """
    # 延迟导入，避免在解析参数时就加载配置
    from app.celery.app import celery_app

    flower_proc: subprocess.Popen | None = None

    # 如果需要 Flower，先后台启动（让 Flower 等待 Worker 就绪）
    if with_flower:
        # 稍微延迟启动 Flower，让 Worker 先初始化
        def delayed_flower_start():
            time.sleep(3)  # 等待 Worker 启动
            nonlocal flower_proc
            flower_proc = start_flower_background(flower_port, flower_auth)

        flower_thread = threading.Thread(target=delayed_flower_start, daemon=True)
        flower_thread.start()

    worker_args = [
        "worker",
        f"--queues={queues}",
        f"--concurrency={concurrency}",
        f"--loglevel={loglevel}",
        f"--pool={pool}",
        "--hostname=ncm-worker@%h",
    ]

    mode_desc = []
    if with_beat:
        worker_args.append("--beat")
        mode_desc.append("Beat")
    if with_flower:
        mode_desc.append(f"Flower@{flower_port}")

    if mode_desc:
        print(f"启动 Celery Worker（含 {' + '.join(mode_desc)}）")
    else:
        print("启动 Celery Worker")

    print(f"队列: {queues}")
    print(f"并发数: {concurrency}")
    print(f"日志级别: {loglevel}")
    print(f"Pool: {pool}")

    try:
        celery_app.worker_main(argv=worker_args)
    finally:
        # Worker 退出时，终止 Flower 子进程
        if flower_proc is not None:
            print("正在关闭 Flower 监控面板...")
            flower_proc.terminate()
            flower_proc.wait(timeout=5)

    return 0


def main() -> int:
    """Celery Worker 启动入口。"""
    parser = argparse.ArgumentParser(
        description="NCM Celery Worker/Beat/Flower 启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  启动 Worker:                uv run start_worker.py
  启动 Worker + Beat:         uv run start_worker.py --beat
  启动 Worker + Flower:       uv run start_worker.py --with-flower
  启动 Worker + Beat + Flower: uv run start_worker.py --beat --with-flower
  启动 Beat (独立):           uv run start_worker.py --beat-only
  启动 Flower (独立):         uv run start_worker.py --flower
  启动 Flower (带认证):       uv run start_worker.py --flower --flower-auth admin:secret
        """,
    )

    # Worker 参数
    parser.add_argument(
        "--queues",
        "-Q",
        default="celery,backup,discovery,topology,deploy",
        help="要处理的队列列表，逗号分隔 (默认: celery,backup,discovery,topology,deploy)",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=4,
        help="Worker 并发数 (默认: 4)",
    )
    parser.add_argument(
        "--loglevel",
        "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)",
    )

    parser.add_argument(
        "--pool",
        default="auto",
        choices=["auto", "prefork", "threads", "solo"],
        help="Worker Pool (Windows 推荐 threads/solo，默认 auto)",
    )

    # Beat 参数
    parser.add_argument(
        "--beat",
        action="store_true",
        help="同时启动 Celery Beat 调度器（内嵌模式，用于单机部署）",
    )
    parser.add_argument(
        "--beat-only",
        action="store_true",
        help="单独启动 Celery Beat 调度器（独立模式，用于分布式部署）",
    )

    # Flower 参数
    parser.add_argument(
        "--flower",
        action="store_true",
        help="单独启动 Flower 监控面板（需要另一终端运行 Worker）",
    )
    parser.add_argument(
        "--with-flower",
        action="store_true",
        help="启动 Worker 时同时启动 Flower 监控面板",
    )
    parser.add_argument(
        "--flower-port",
        type=int,
        default=5555,
        help="Flower 监控面板端口 (默认: 5555)",
    )
    parser.add_argument(
        "--flower-auth",
        type=str,
        default=None,
        help="Flower HTTP Basic Auth，格式: user:password",
    )

    args = parser.parse_args()

    # Windows 上 prefork/billiard 常出现 WinError 5/6（句柄/权限/信号限制），默认切到 threads。
    if args.pool == "auto":
        pool = "threads" if sys.platform.startswith("win") else "prefork"
    else:
        pool = args.pool

    # 检查互斥参数
    modes = sum([args.flower, args.beat_only])
    if modes > 1:
        parser.error("--flower 和 --beat-only 不能同时使用")

    # 执行相应模式
    if args.flower:
        return start_flower(args.flower_port, args.flower_auth)

    if args.beat_only:
        return start_beat_only()

    return start_worker(
        queues=args.queues,
        concurrency=args.concurrency,
        loglevel=args.loglevel,
        pool=pool,
        with_beat=args.beat,
        with_flower=args.with_flower,
        flower_port=args.flower_port,
        flower_auth=args.flower_auth,
    )


if __name__ == "__main__":
    sys.exit(main())
