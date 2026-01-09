"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: start_worker.py
@DateTime: 2026-01-09 11:55:00
@Docs: Celery Worker 启动脚本.

使用方式:
    # 启动默认 Worker (处理所有队列)
    uv run start_worker.py

    # 启动指定队列的 Worker
    uv run start_worker.py --queues backup,discovery

    # 启动并指定并发数
    uv run start_worker.py --concurrency 8

    # 启动 Flower 监控面板
    uv run start_worker.py --flower
"""

import argparse
import subprocess
import sys


def main() -> int:
    """Celery Worker 启动入口。"""
    parser = argparse.ArgumentParser(description="NCM Celery Worker 启动脚本")
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
    parser.add_argument(
        "--flower",
        action="store_true",
        help="启动 Flower 监控面板而非 Worker",
    )
    parser.add_argument(
        "--flower-port",
        type=int,
        default=5555,
        help="Flower 监控面板端口 (默认: 5555)",
    )
    parser.add_argument(
        "--beat",
        action="store_true",
        help="同时启动 Celery Beat 调度器 (用于定时任务)",
    )

    args = parser.parse_args()

    if args.flower:
        # 使用 subprocess 启动 Flower（避免直接导入 FlowerCommand 的兼容性问题）
        flower_cmd = [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.celery.app:celery_app",
            "flower",
            f"--port={args.flower_port}",
        ]
        print(f"启动 Flower 监控面板: {' '.join(flower_cmd)}")
        return subprocess.call(flower_cmd)
    else:
        # 导入 Celery 应用 (延迟导入，避免在解析参数时就加载配置)
        from app.celery.app import celery_app

        # 启动 Worker
        worker_args = [
            "worker",
            f"--queues={args.queues}",
            f"--concurrency={args.concurrency}",
            f"--loglevel={args.loglevel}",
            "--hostname=ncm-worker@%h",
        ]

        if args.beat:
            worker_args.append("--beat")

        celery_app.worker_main(argv=worker_args)
        return 0


if __name__ == "__main__":
    sys.exit(main())
