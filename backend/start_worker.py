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
    uv run start_worker.py --queues backup,discovery

    # 启动并指定并发数
    uv run start_worker.py --concurrency 8

    # 启动 Worker + Beat（内嵌定时任务调度）
    uv run start_worker.py --beat

    # 单独启动 Beat 调度器（用于分布式部署）
    uv run start_worker.py --beat-only

    # 启动 Flower 监控面板
    uv run start_worker.py --flower

    # 启动 Flower（带 HTTP Basic Auth）
    uv run start_worker.py --flower --flower-auth admin:password
"""

import argparse
import subprocess
import sys


def start_flower(port: int, basic_auth: str | None = None) -> int:
    """
    启动 Flower 监控面板。

    Args:
        port: Flower Web UI 端口
        basic_auth: HTTP Basic Auth 认证，格式 "user:password"

    Returns:
        int: 进程退出码
    """
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

    print(f"启动 Flower 监控面板: http://localhost:{port}")
    print(f"命令: {' '.join(flower_cmd)}")
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
    with_beat: bool = False,
) -> int:
    """
    启动 Celery Worker。

    Args:
        queues: 要处理的队列列表，逗号分隔
        concurrency: Worker 并发数
        loglevel: 日志级别
        with_beat: 是否同时启动 Beat 调度器

    Returns:
        int: 进程退出码
    """
    # 延迟导入，避免在解析参数时就加载配置
    from app.celery.app import celery_app

    worker_args = [
        "worker",
        f"--queues={queues}",
        f"--concurrency={concurrency}",
        f"--loglevel={loglevel}",
        "--hostname=ncm-worker@%h",
    ]

    if with_beat:
        worker_args.append("--beat")
        print("启动 Celery Worker（内嵌 Beat 调度器）")
    else:
        print("启动 Celery Worker")

    print(f"队列: {queues}")
    print(f"并发数: {concurrency}")
    print(f"日志级别: {loglevel}")

    celery_app.worker_main(argv=worker_args)
    return 0


def main() -> int:
    """Celery Worker 启动入口。"""
    parser = argparse.ArgumentParser(
        description="NCM Celery Worker/Beat/Flower 启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  启动 Worker:           uv run start_worker.py
  启动 Worker + Beat:    uv run start_worker.py --beat
  启动 Beat (独立):      uv run start_worker.py --beat-only
  启动 Flower:           uv run start_worker.py --flower
  启动 Flower (带认证):  uv run start_worker.py --flower --flower-auth admin:secret
        """,
    )

    # Worker 参数
    parser.add_argument(
        "--queues",
        "-Q",
        default="celery,backup,discovery,topology",
        help="要处理的队列列表，逗号分隔 (默认: celery,backup,discovery,topology)",
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
        help="启动 Flower 监控面板",
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
        with_beat=args.beat,
    )


if __name__ == "__main__":
    sys.exit(main())
