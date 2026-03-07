#!/usr/bin/env python3
"""
DAG Diff — 对比两个版本的DAG，输出结构化changelog。

用法:
  # 对比当前DAG vs 最近一次快照
  python scripts/dag_diff.py

  # 对比两个指定文件
  python scripts/dag_diff.py data/history/old.json data/dag.json

  # JSON输出(供程序消费)
  python scripts/dag_diff.py --json
"""

import json
import sys
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_dag(path):
    with open(path) as f:
        return json.load(f)


def get_latest_history():
    """获取 history/ 中最新的快照。"""
    hist_dir = DATA_DIR / "history"
    snapshots = sorted(hist_dir.glob("*.json"), reverse=True)
    if not snapshots:
        return None
    return snapshots[0]


def diff_dags(old, new):
    """对比两个DAG，返回结构化diff。"""
    old_nodes = old.get("nodes", {})
    new_nodes = new.get("nodes", {})
    old_edge_set = {(e["source"], e["target"]) for e in old.get("edges", [])}
    new_edge_set = {(e["source"], e["target"]) for e in new.get("edges", [])}
    old_edge_map = {(e["source"], e["target"]): e for e in old.get("edges", [])}
    new_edge_map = {(e["source"], e["target"]): e for e in new.get("edges", [])}

    result = {
        "old_version": old.get("version", "?"),
        "new_version": new.get("version", "?"),
        "old_counts": {"nodes": len(old_nodes), "edges": len(old.get("edges", []))},
        "new_counts": {"nodes": len(new_nodes), "edges": len(new.get("edges", []))},
        "added_nodes": [],
        "removed_nodes": [],
        "prob_changes": [],
        "added_edges": [],
        "removed_edges": [],
        "weight_changes": [],
    }

    # Node additions/removals
    for nid in new_nodes:
        if nid not in old_nodes:
            n = new_nodes[nid]
            result["added_nodes"].append({
                "id": nid,
                "label": n.get("label", ""),
                "probability": n.get("probability", 0),
                "domains": n.get("domains", []),
            })

    for nid in old_nodes:
        if nid not in new_nodes:
            n = old_nodes[nid]
            result["removed_nodes"].append({
                "id": nid,
                "label": n.get("label", ""),
            })

    # Probability changes
    for nid in new_nodes:
        if nid in old_nodes:
            old_p = old_nodes[nid].get("probability", 0)
            new_p = new_nodes[nid].get("probability", 0)
            delta = new_p - old_p
            if abs(delta) >= 0.01:  # 1% threshold
                result["prob_changes"].append({
                    "id": nid,
                    "label": new_nodes[nid].get("label", ""),
                    "old": old_p,
                    "new": new_p,
                    "delta": delta,
                })

    # Sort prob changes by absolute delta
    result["prob_changes"].sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Edge additions/removals
    for key in new_edge_set - old_edge_set:
        e = new_edge_map[key]
        sl = new_nodes.get(key[0], {}).get("label", key[0])[:25]
        tl = new_nodes.get(key[1], {}).get("label", key[1])[:25]
        result["added_edges"].append({
            "source": key[0], "target": key[1],
            "source_label": sl, "target_label": tl,
            "weight": e.get("weight", 0),
        })

    for key in old_edge_set - new_edge_set:
        sl = old_nodes.get(key[0], {}).get("label", key[0])[:25]
        tl = old_nodes.get(key[1], {}).get("label", key[1])[:25]
        result["removed_edges"].append({
            "source": key[0], "target": key[1],
            "source_label": sl, "target_label": tl,
        })

    # Weight changes on existing edges
    for key in new_edge_set & old_edge_set:
        old_w = old_edge_map[key].get("weight", 0)
        new_w = new_edge_map[key].get("weight", 0)
        if abs(new_w - old_w) >= 0.01:
            sl = new_nodes.get(key[0], {}).get("label", key[0])[:25]
            tl = new_nodes.get(key[1], {}).get("label", key[1])[:25]
            result["weight_changes"].append({
                "source": key[0], "target": key[1],
                "source_label": sl, "target_label": tl,
                "old": old_w, "new": new_w,
                "delta": new_w - old_w,
            })

    return result


def format_diff(d):
    """格式化diff为人类可读文本。"""
    lines = []
    lines.append(f"📊 DAG Diff: v{d['old_version']} → v{d['new_version']}")
    lines.append(f"   {d['old_counts']['nodes']}n/{d['old_counts']['edges']}e → {d['new_counts']['nodes']}n/{d['new_counts']['edges']}e")
    lines.append("")

    if d["added_nodes"]:
        lines.append(f"➕ 新增节点 ({len(d['added_nodes'])})")
        for n in d["added_nodes"]:
            lines.append(f"   {n['probability']:.0%} {n['label']} [{','.join(n['domains'])}]")
        lines.append("")

    if d["removed_nodes"]:
        lines.append(f"➖ 删除节点 ({len(d['removed_nodes'])})")
        for n in d["removed_nodes"]:
            lines.append(f"   {n['label']}")
        lines.append("")

    if d["prob_changes"]:
        # Split into significant (>=10%) and minor
        sig = [p for p in d["prob_changes"] if abs(p["delta"]) >= 0.10]
        minor = [p for p in d["prob_changes"] if abs(p["delta"]) < 0.10]
        
        if sig:
            lines.append(f"🔴 概率显著变化 (≥10%, {len(sig)}个)")
            for p in sig:
                arrow = "↑" if p["delta"] > 0 else "↓"
                lines.append(f"   {p['old']:.0%}→{p['new']:.0%} ({arrow}{abs(p['delta']):.0%}) {p['label']}")
            lines.append("")
        
        if minor:
            lines.append(f"🟡 概率微调 (<10%, {len(minor)}个)")
            for p in minor:
                arrow = "↑" if p["delta"] > 0 else "↓"
                lines.append(f"   {p['old']:.0%}→{p['new']:.0%} ({arrow}{abs(p['delta']):.0%}) {p['label']}")
            lines.append("")

    if d["added_edges"]:
        lines.append(f"🔗 新增边 ({len(d['added_edges'])})")
        for e in d["added_edges"]:
            lines.append(f"   {e['source_label']} →({e['weight']}) {e['target_label']}")
        lines.append("")

    if d["removed_edges"]:
        lines.append(f"✂️ 删除边 ({len(d['removed_edges'])})")
        for e in d["removed_edges"]:
            lines.append(f"   {e['source_label']} → {e['target_label']}")
        lines.append("")

    if d["weight_changes"]:
        lines.append(f"⚖️ 边权重变化 ({len(d['weight_changes'])})")
        for e in d["weight_changes"]:
            arrow = "↑" if e["delta"] > 0 else "↓"
            lines.append(f"   {e['source_label']}→{e['target_label']}: {e['old']:.2f}→{e['new']:.2f} ({arrow}{abs(e['delta']):.2f})")
        lines.append("")

    if not any([d["added_nodes"], d["removed_nodes"], d["prob_changes"], d["added_edges"], d["removed_edges"], d["weight_changes"]]):
        lines.append("   无变化")

    return "\n".join(lines)


def main():
    json_mode = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if len(args) == 2:
        old = load_dag(args[0])
        new = load_dag(args[1])
    elif len(args) == 0:
        hist = get_latest_history()
        if not hist:
            print("ERROR: 无历史快照可对比。")
            sys.exit(1)
        old = load_dag(hist)
        new = load_dag(DATA_DIR / "dag.json")
        print(f"(对比: {hist.name} vs dag.json)\n")
    else:
        print("用法: dag_diff.py [old.json new.json] [--json]")
        sys.exit(1)

    d = diff_dags(old, new)

    if json_mode:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    else:
        print(format_diff(d))


if __name__ == "__main__":
    main()
