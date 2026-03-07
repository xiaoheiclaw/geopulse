#!/usr/bin/env python3
"""
报告生成器 — 从 DAG + RunOutput 自动生成态势报告骨架。

用法:
  python scripts/gen_report.py                  # 输出到stdout
  python scripts/gen_report.py -o docs/report_20260307.md  # 输出到文件
"""

import json
import sys
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_dag():
    return json.load(open(DATA_DIR / "dag.json"))


def load_latest_run():
    runs_dir = DATA_DIR / "runs"
    runs = [f for f in runs_dir.iterdir() if f.suffix == ".json"]
    if not runs:
        return None
    runs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return json.load(open(runs[0]))


def build_adjacency(dag):
    children = defaultdict(list)
    parents = defaultdict(list)
    for e in dag["edges"]:
        children[e["source"]].append((e["target"], e.get("weight", 0)))
        parents[e["target"]].append((e["source"], e.get("weight", 0)))
    return children, parents


def find_main_chain(dag):
    """找到从 event 到最深叶子的最高权重路径。"""
    nodes = dag["nodes"]
    children, parents = build_adjacency(dag)
    
    # Start from event nodes
    events = [nid for nid, n in nodes.items() if n["node_type"] == "event"]
    
    best_chain = []
    
    def dfs(nid, path):
        nonlocal best_chain
        if len(path) > len(best_chain):
            best_chain = path[:]
        for child, w in sorted(children.get(nid, []), key=lambda x: -x[1]):
            if child not in [p[0] for p in path]:
                dfs(child, path + [(child, nodes[child]["probability"])])
    
    for ev in events:
        dfs(ev, [(ev, nodes[ev]["probability"])])
    
    return best_chain


def format_chain(chain, nodes):
    """格式化传导链。"""
    lines = []
    for i, (nid, prob) in enumerate(chain):
        label = nodes[nid]["label"][:35]
        if i == 0:
            lines.append(f"{label} {prob:.0%}")
        else:
            prev_prob = chain[i-1][1]
            delta = prob - prev_prob
            arrow = "↑" if delta > 0 else "↓"
            lines.append(f"  {arrow} {abs(delta):.0%}")
            lines.append(f"{label} {prob:.0%}")
    return "\n".join(lines)


def gen_report(dag, run):
    nodes = dag["nodes"]
    edges = dag["edges"]
    children, parents = build_adjacency(dag)
    now = datetime.now(timezone.utc)
    
    # Stats
    n_nodes = len(nodes)
    n_edges = len(edges)
    version = dag.get("version", "?")
    events = {nid: n for nid, n in nodes.items() if n["node_type"] == "event"}
    states = {nid: n for nid, n in nodes.items() if n["node_type"] == "state"}
    preds = {nid: n for nid, n in nodes.items() if n["node_type"] == "prediction"}
    
    # Leaves
    child_set = {e["source"] for e in edges}
    leaves = [nid for nid in nodes if nid not in child_set]
    
    lines = []
    lines.append("# GeoPulse 态势报告")
    lines.append("")
    lines.append(f"**生成时间: {now.strftime('%Y-%m-%d %H:%M UTC')}**")
    lines.append(f"**DAG v{version} · {n_nodes} 节点 / {n_edges} 边**")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # === Section 1: Key States ===
    lines.append("## 一、关键状态节点")
    lines.append("")
    lines.append("| 节点 | 概率 | 置信度 | 趋势 |")
    lines.append("|------|------|--------|------|")
    for nid, n in sorted(states.items(), key=lambda x: -x[1]["probability"]):
        lines.append(f"| {n['label'][:40]} | {n['probability']:.0%} | {n['confidence']:.0%} | — |")
    lines.append("")
    
    # === Section 2: Predictions ===
    lines.append("## 二、预测节点（按概率排序）")
    lines.append("")
    lines.append("| 节点 | 概率 | 时间窗 | 领域 |")
    lines.append("|------|------|--------|------|")
    for nid, n in sorted(preds.items(), key=lambda x: -x[1]["probability"]):
        domains = ",".join(n.get("domains", []))
        th = n.get("time_horizon", "—")
        lines.append(f"| {n['label'][:40]} | {n['probability']:.0%} | {th} | {domains} |")
    lines.append("")
    
    # === Section 3: Main Chain ===
    lines.append("## 三、主传导链")
    lines.append("")
    lines.append("```")
    chain = find_main_chain(dag)
    if chain:
        for i, (nid, prob) in enumerate(chain[:12]):  # cap at 12
            label = nodes[nid]["label"][:40]
            if i == 0:
                lines.append(f"{label} {prob:.0%}")
            else:
                prev_prob = chain[i-1][1]
                delta = prob - prev_prob
                sign = "+" if delta >= 0 else ""
                lines.append(f"  → ({sign}{delta:.0%})")
                lines.append(f"{label} {prob:.0%}")
    lines.append("```")
    lines.append("")
    
    # === Section 4: Scenarios ===
    if run and "scenarios" in run:
        lines.append("## 四、场景权重")
        lines.append("")
        lines.append("| 场景 | 权重 | 关键假设 |")
        lines.append("|------|------|---------|")
        for s in run["scenarios"]:
            w = s.get("weight", 0)
            assumption = s.get("key_assumptions", ["—"])[0] if s.get("key_assumptions") else "—"
            lines.append(f"| {s['label']} | {w:.0%} | {assumption[:50]} |")
        lines.append("")
    
    # === Section 5: Bottlenecks ===
    if run and "bottlenecks" in run:
        lines.append("## 五、瓶颈节点")
        lines.append("")
        for b in run["bottlenecks"][:5]:
            lines.append(f"- **{b['node_id']}** ({b.get('label', '')}): {b.get('why', '')[:60]}")
        lines.append("")
    
    # === Section 6: Triggers ===
    if run and "execution_plan" in run:
        triggers = run["execution_plan"].get("triggers", [])
        if triggers:
            lines.append("## 六、领先信号触发器")
            lines.append("")
            lines.append("| ID | 信号 | 动作 | 领先时间 |")
            lines.append("|----|------|------|---------|")
            for t in triggers:
                tid = t.get("trigger_id", "?")
                sig = t.get("signal", "")[:40]
                act = t.get("action", "")[:40]
                lt = t.get("lead_time", "—")
                lines.append(f"| {tid} | {sig} | {act} | {lt} |")
            lines.append("")
    
    # === Section 7: Evidence gaps ===
    no_evidence = [nid for nid, n in nodes.items() 
                   if n["node_type"] != "event" and not n.get("evidence")]
    if no_evidence:
        lines.append("## 七、数据缺口")
        lines.append("")
        lines.append(f"{len(no_evidence)} 个节点缺少证据来源:")
        lines.append("")
        for nid in no_evidence[:10]:
            lines.append(f"- {nid}: {nodes[nid]['label'][:40]}")
        if len(no_evidence) > 10:
            lines.append(f"- ...及其他 {len(no_evidence)-10} 个")
        lines.append("")
    
    # === Footer ===
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by `scripts/gen_report.py` at {now.isoformat()}*")
    lines.append(f"*Red team audit: run `python -c \"from geopulse.red_team import audit_dag; ...\"` to verify*")
    
    return "\n".join(lines)


def main():
    dag = load_dag()
    run = load_latest_run()
    
    report = gen_report(dag, run)
    
    # Output
    out_flag = "-o" in sys.argv
    if out_flag:
        idx = sys.argv.index("-o")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]
            with open(out_path, "w") as f:
                f.write(report)
            print(f"Report written to {out_path}")
            return
    
    print(report)


if __name__ == "__main__":
    main()
