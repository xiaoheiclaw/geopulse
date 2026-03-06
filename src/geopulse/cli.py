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
    subparsers = parser.add_subparsers(dest="command")

    # ── Legacy commands (kept for backward compat) ──
    subparsers.add_parser("run", help="执行 MVP pipeline")
    subparsers.add_parser("report", help="生成报告")
    sub_node = subparsers.add_parser("node", help="查看节点详情")
    sub_node.add_argument("--node-id", required=True, help="节点ID")
    subparsers.add_parser("status", help="DAG 状态")
    subparsers.add_parser("ingest", help="仅抓取新闻")
    sub_apply = subparsers.add_parser("apply", help="应用外部分析结果")
    sub_apply.add_argument("--json-input", help="JSON 输入内容")
    sub_apply.add_argument("--json-file", help="JSON 输入文件")

    # ── v7.4 commands ──
    v74_parser = subparsers.add_parser("v74", help="v7.4 Pipeline 命令")
    v74_sub = v74_parser.add_subparsers(dest="v74_command")

    v74_run = v74_sub.add_parser("run", help="完整 v7.4 运行")
    v74_run.add_argument(
        "--trigger",
        choices=["scheduled", "event_driven", "manual"],
        default="scheduled",
        help="触发类型",
    )
    v74_run.add_argument("--event", help="触发事件描述")
    v74_run.add_argument("--model", help="模型覆盖（如 claude-haiku-4-5-20251001）")

    v74_prepare = v74_sub.add_parser("prepare", help="只准备 context（调试用）")
    v74_prepare.add_argument("--output", help="输出 JSON 文件路径")
    v74_prepare.add_argument(
        "--trigger",
        choices=["scheduled", "event_driven", "manual"],
        default="scheduled",
    )

    v74_validate = v74_sub.add_parser("validate", help="验证 RunOutput JSON")
    v74_validate.add_argument("file", help="RunOutput JSON 文件路径")

    v74_process = v74_sub.add_parser("process", help="处理 Agent 输出")
    v74_process.add_argument("file", help="RunOutput JSON 文件路径")
    v74_process.add_argument(
        "--trigger",
        choices=["scheduled", "event_driven", "manual"],
        default="scheduled",
    )

    v74_sub.add_parser("shs", help="查看 Standing Hypothesis Set")
    v74_sub.add_parser("registry", help="查看 Registry 信用评分")

    # Common options
    parser.add_argument("--data-dir", default="data", help="数据目录")
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    readwise_token = os.getenv("READWISE_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "") or None

    if args.command == "v74":
        _handle_v74(args, anthropic_key, base_url)
    else:
        _handle_legacy(args, readwise_token, anthropic_key, base_url)


def _handle_v74(args, anthropic_key: str, base_url: str | None):
    """Handle v7.4 subcommands."""
    if not args.v74_command:
        print("用法: geopulse v74 {run|prepare|validate|process|shs|registry}")
        sys.exit(1)

    if args.v74_command == "run":
        if not anthropic_key:
            print("错误：需要设置 ANTHROPIC_API_KEY")
            sys.exit(1)
        from .orchestrator import Orchestrator
        from .run_output import TriggerType

        model_kwargs = {}
        if getattr(args, "model", None):
            model_kwargs["model"] = args.model
        orch = Orchestrator(
            data_dir=args.data_dir,
            anthropic_api_key=anthropic_key,
            base_url=base_url,
            **model_kwargs,
        )
        trigger = TriggerType(args.trigger)
        result = orch.run(trigger_type=trigger, trigger_event=args.event)
        print(f"Run completed: {result.meta.run_id}")
        print(f"  Trigger: {result.meta.trigger_type.value}")
        print(f"  Evidence: {result.meta.evidence_count}")
        print(f"  Scenarios: {len(result.scenarios)}")
        print(f"  Regime: {result.regime.current.value}")
        print(f"  Duration: {result.meta.run_duration_ms}ms")
        print(f"  Models loaded: {result.model_trace.total_model_calls}")

    elif args.v74_command == "prepare":
        from .orchestrator import Orchestrator
        from .run_output import TriggerType

        orch = Orchestrator(data_dir=args.data_dir)
        trigger = TriggerType(args.trigger)
        context = orch.prepare_context(trigger_type=trigger)
        ctx_json = context.model_dump_json(indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(ctx_json)
            print(f"Context written to {args.output}")
        else:
            print(ctx_json)

    elif args.v74_command == "validate":
        from .run_output import RunOutput

        try:
            with open(args.file, "r") as f:
                raw = f.read()
            output = RunOutput.model_validate_json(raw)
            print(f"Valid RunOutput: {output.meta.run_id}")
            print(f"  Scenarios: {len(output.scenarios)}")
            print(f"  Bottlenecks: {len(output.bottlenecks)}")
            print(f"  Model calls: {output.model_trace.total_model_calls}")
        except Exception as e:
            print(f"Validation failed: {e}")
            sys.exit(1)

    elif args.v74_command == "process":
        from .orchestrator import Orchestrator
        from .run_output import TriggerType

        orch = Orchestrator(
            data_dir=args.data_dir,
            anthropic_api_key=anthropic_key or "unused",
        )
        trigger = TriggerType(args.trigger)
        context = orch.prepare_context(trigger_type=trigger)
        with open(args.file, "r") as f:
            raw = f.read()
        result = orch.process_output(raw, context)
        print(f"Processed: {result.meta.run_id}")
        print(f"  Archived to: data/runs/{result.meta.run_id}.json")

    elif args.v74_command == "shs":
        from .shs import SHSStorage

        storage = SHSStorage(data_dir=args.data_dir)
        hypotheses = storage.load()
        if not hypotheses:
            print("SHS 为空。")
        else:
            for h in hypotheses:
                status_icon = "🟢" if h.status == "active" else "⚪"
                print(f"{status_icon} [{h.id}] {h.label}")
                print(f"    置信度: {h.confidence:.2f} | 时间窗: {h.horizon}")
                print(f"    {h.statement[:80]}...")
                print()

    elif args.v74_command == "registry":
        from .registry import Registry

        registry = Registry(f"{args.data_dir}/registry.json")
        models = registry.load()
        if not models:
            print("Registry 为空。")
        else:
            for m in models.values():
                ao = " [always-on]" if m.always_on else ""
                print(
                    f"  {m.id:25s} {m.role.value}/{m.cost.value:6s} "
                    f"credit={m.credit_score:.3f}{ao}"
                )


def _handle_legacy(args, readwise_token: str, anthropic_key: str, base_url: str | None):
    """Handle legacy MVP commands."""
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
        if not getattr(args, "json_input", None) and not getattr(args, "json_file", None):
            print("错误：apply 命令需要 --json-input 或 --json-file")
            sys.exit(1)
        from .pipeline import Pipeline

        try:
            if args.json_file:
                with open(args.json_file, "r") as f:
                    input_data = json.load(f)
            else:
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
