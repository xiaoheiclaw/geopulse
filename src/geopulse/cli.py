"""CLI entry point for GeoPulse."""
from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv


def main():
    """Main CLI entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="GeoPulse — 地缘政治概率追踪")
    parser.add_argument(
        "command",
        choices=["run", "report", "node", "status", "ingest", "apply"],
        help="run=执行pipeline, report=生成报告, node=查看节点, status=DAG状态, ingest=仅抓取新闻, apply=应用外部分析结果",
    )
    parser.add_argument("--node-id", help="节点ID（用于 node 命令）")
    parser.add_argument("--data-dir", default="data", help="数据目录")
    parser.add_argument("--json-input", help="JSON 输入内容 (用于 apply 命令)")
    args = parser.parse_args()

    readwise_token = os.getenv("READWISE_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "") or None

    if args.command == "run":
        if not readwise_token or not anthropic_key:
            print("错误：需要设置 READWISE_TOKEN 和 ANTHROPIC_API_KEY")
            sys.exit(1)
        from .pipeline import Pipeline

        pipeline = Pipeline(
            readwise_token=readwise_token,
            anthropic_api_key=anthropic_key,
            data_dir=args.data_dir,
            base_url=base_url,
        )
        report = pipeline.run()
        if report:
            print(report)
        else:
            print("无新事件。")

    elif args.command == "ingest":
        if not readwise_token:
            print("错误：需要设置 READWISE_TOKEN")
            sys.exit(1)
        from .ingester import ReadwiseIngester
        ingester = ReadwiseIngester(token=readwise_token)
        articles = ingester.fetch()
        print(json.dumps(articles, ensure_ascii=False, indent=2))

    elif args.command == "apply":
        if not args.json_input:
            print("错误：apply 命令需要 --json-input")
            sys.exit(1)
        from .pipeline import Pipeline

        try:
            input_data = json.loads(args.json_input)
        except Exception as e:
            print(f"JSON 解析错误: {e}")
            sys.exit(1)
            
        pipeline = Pipeline(
            readwise_token=readwise_token,
            anthropic_api_key=anthropic_key,
            data_dir=args.data_dir,
            base_url=base_url,
        )
        report = pipeline.apply_external_analysis(input_data)
        if report:
            print(report)
        else:
            print("更新失败。")

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
