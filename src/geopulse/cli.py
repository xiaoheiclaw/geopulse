"""CLI entry point for GeoPulse."""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


def main():
    """Main CLI entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="GeoPulse — 地缘政治概率追踪")
    parser.add_argument(
        "command",
        choices=["run", "report", "node", "status"],
        help="run=执行pipeline, report=生成报告, node=查看节点, status=DAG状态",
    )
    parser.add_argument("--node-id", help="节点ID（用于 node 命令）")
    parser.add_argument("--data-dir", default="data", help="数据目录")
    args = parser.parse_args()

    readwise_token = os.getenv("READWISE_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if args.command == "run":
        if not readwise_token or not anthropic_key:
            print("错误：需要设置 READWISE_TOKEN 和 ANTHROPIC_API_KEY")
            sys.exit(1)
        from .pipeline import Pipeline

        pipeline = Pipeline(
            readwise_token=readwise_token,
            anthropic_api_key=anthropic_key,
            data_dir=args.data_dir,
        )
        report = pipeline.run()
        if report:
            print(report)
        else:
            print("无新事件。")

    elif args.command == "report":
        from .reporter import Reporter
        from .storage import DAGStorage

        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。先运行 geopulse run")
            sys.exit(1)
        reporter = Reporter()
        print(reporter.daily_report(dag))

    elif args.command == "node":
        if not args.node_id:
            print("需要指定 --node-id")
            sys.exit(1)
        from .reporter import Reporter
        from .storage import DAGStorage

        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。")
            sys.exit(1)
        reporter = Reporter()
        print(reporter.node_detail(dag, args.node_id))

    elif args.command == "status":
        from .storage import DAGStorage

        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。")
        else:
            orders = dag.compute_orders()
            print(f"场景: {dag.scenario_label}")
            print(f"版本: {dag.version}")
            print(f"节点数: {len(dag.nodes)}")
            print(f"边数: {len(dag.edges)}")
            print(f"最大阶数: {max(orders.values()) if orders else 0}")
            print(f"全局风险: {dag.global_risk_index():.0f}/100")


if __name__ == "__main__":
    main()
