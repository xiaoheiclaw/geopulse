#!/usr/bin/env python3
"""
GeoPulse 综合红队审计 v2
合并三层审计: 结构审计 + 概率审计 + 信号审计
每次DAG/RunOutput更新后运行。
"""

import json
import sys
import os
from collections import deque, defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_dag():
    return json.load(open(os.path.join(DATA_DIR, "dag.json")))


def load_run():
    runs_dir = os.path.join(DATA_DIR, "runs")
    runs = [f for f in os.listdir(runs_dir) if f.endswith(".json")]
    if runs:
        # Use most recently modified file
        runs.sort(key=lambda f: os.path.getmtime(os.path.join(runs_dir, f)), reverse=True)
        path = os.path.join(runs_dir, runs[0])
        print(f"  (loading {runs[0]})")
        return json.load(open(path))
    return None


# ═══════════════════════════════════════════
# LAYER 1: DAG 结构审计
# ═══════════════════════════════════════════

def audit_dag_structure(dag):
    nodes = dag["nodes"]
    edges = dag["edges"]
    errors, warnings = [], []

    adj = defaultdict(list)
    parents = defaultdict(list)
    for e in edges:
        adj[e["source"]].append(e["target"])
        parents[e["target"]].append(e["source"])

    # 1.1 Cycle detection
    visited, rec = set(), set()
    def dfs(v, path):
        visited.add(v); rec.add(v)
        for u in adj.get(v, []):
            if u not in visited:
                dfs(u, path + [u])
            elif u in rec:
                cycle = " → ".join(path[path.index(u):] + [u])
                errors.append(f"CYCLE: {cycle}")
        rec.discard(v)
    for v in nodes:
        if v not in visited:
            dfs(v, [v])

    # 1.2 Orphan nodes
    connected = set()
    for e in edges:
        connected.add(e["source"])
        connected.add(e["target"])
    for nid in nodes:
        if nid not in connected:
            errors.append(f"ORPHAN: {nid}")

    # 1.3 Edge validity
    for e in edges:
        if e["source"] not in nodes:
            errors.append(f"EDGE_MISSING_SOURCE: {e['source']}")
        if e["target"] not in nodes:
            errors.append(f"EDGE_MISSING_TARGET: {e['target']}")
        w = e.get("weight", 0)
        if w <= 0 or w > 1:
            errors.append(f"EDGE_WEIGHT: {e['source']}→{e['target']} w={w}")

    # 1.4 Event nodes = 100%
    for nid, n in nodes.items():
        if n["node_type"] == "event" and n["probability"] != 1.0:
            errors.append(f"EVENT≠100: {nid} = {n['probability']}")

    # 1.5 Prob range
    for nid, n in nodes.items():
        p = n["probability"]
        if p < 0 or p > 1:
            errors.append(f"PROB_RANGE: {nid} = {p}")

    # 1.6 Leaf ratio
    leaves = [nid for nid in nodes if nid not in adj]
    leaf_pct = len(leaves) / len(nodes) if nodes else 0
    if leaf_pct > 0.30:
        warnings.append(f"LEAF_RATIO: {leaf_pct:.0%} ({len(leaves)}/{len(nodes)}) > 30%")

    # 1.7 Max depth
    roots = [nid for nid in nodes if nid not in parents]
    max_d = 0
    for r in roots:
        q = deque([(r, 0)])
        vis = {r}
        while q:
            v, d = q.popleft()
            max_d = max(max_d, d)
            for u in adj.get(v, []):
                if u not in vis:
                    vis.add(u)
                    q.append((u, d + 1))

    return errors, warnings, {
        "nodes": len(nodes),
        "edges": len(edges),
        "roots": len(roots),
        "leaves": len(leaves),
        "leaf_pct": leaf_pct,
        "max_depth": max_d,
    }


# ═══════════════════════════════════════════
# LAYER 2: DAG 概率审计
# ═══════════════════════════════════════════

def audit_dag_probabilities(dag):
    nodes = dag["nodes"]
    edges = dag["edges"]
    errors, warnings = [], []

    # 2.1 Node threshold definitions
    no_def = []
    for nid, n in nodes.items():
        if n["node_type"] != "event" and "定义:" not in n.get("reasoning", ""):
            no_def.append(nid)
            errors.append(f"NO_DEFINITION: {nid} ({n['label']})")

    # 2.2 Low decay edges (<4%)
    low_decay = []
    for e in edges:
        sp = nodes.get(e["source"], {}).get("probability", 0)
        tp = nodes.get(e["target"], {}).get("probability", 0)
        st = nodes.get(e["source"], {}).get("node_type", "")
        if abs(sp - tp) < 0.04 and sp > 0 and st != "event":
            low_decay.append(f"{e['source']}({sp:.0%})→{e['target']}({tp:.0%})")
            warnings.append(f"LOW_DECAY: {e['source']}({sp:.0%})→{e['target']}({tp:.0%})")

    # 2.3 Cross-domain without bridge
    cross = []
    for e in edges:
        s = nodes.get(e["source"], {})
        t = nodes.get(e["target"], {})
        sd = set(s.get("domains", []))
        td = set(t.get("domains", []))
        if sd and td and not sd.intersection(td) and s.get("node_type") != "event":
            cross.append(f"{e['source']}→{e['target']}")
            warnings.append(f"CROSS_DOMAIN: {e['source']}[{','.join(sd)}]→{e['target']}[{','.join(td)}]")

    # 2.4 Evidence missing
    no_evidence = []
    for nid, n in nodes.items():
        if n["node_type"] != "event" and not n.get("evidence"):
            no_evidence.append(nid)
            warnings.append(f"NO_EVIDENCE: {nid}")

    # 2.5 Probability distribution check
    non_event_probs = sorted([n["probability"] for n in nodes.values() if n["node_type"] != "event"])
    if non_event_probs:
        spread = non_event_probs[-1] - non_event_probs[0]
        median = non_event_probs[len(non_event_probs) // 2]
        high_cluster = sum(1 for p in non_event_probs if p > 0.9)
        if high_cluster > len(non_event_probs) * 0.5:
            warnings.append(f"CALIBRATION: {high_cluster}/{len(non_event_probs)} nodes >90% — 缺乏区分度")

    return errors, warnings, {
        "no_definition": len(no_def),
        "low_decay": len(low_decay),
        "cross_domain": len(cross),
        "no_evidence": len(no_evidence),
        "prob_min": non_event_probs[0] if non_event_probs else 0,
        "prob_median": median if non_event_probs else 0,
        "prob_max": non_event_probs[-1] if non_event_probs else 0,
    }


# ═══════════════════════════════════════════
# LAYER 3: 信号/触发器审计
# ═══════════════════════════════════════════

def audit_signals(run):
    if not run:
        return [], ["NO_RUN: 无RunOutput可审计"], {}

    errors, warnings = [], []
    triggers = run.get("execution_plan", {}).get("triggers", [])

    # 3.1 Threshold check
    for t in triggers:
        tid = t.get("trigger_id", "?")
        sig = t.get("signal", "")
        has_threshold = any(c in sig for c in [">", "<", "=", "%", "vol", "bp", "艘", "天", "x", "次", "家", "桶"])
        if not has_threshold:
            errors.append(f"SIGNAL_NO_THRESHOLD: {tid}")

    # 3.2 Action specificity
    for t in triggers:
        tid = t.get("trigger_id", "?")
        act = t.get("action", "")
        specific = any(v in act for v in ["加仓", "减仓", "建仓", "退出", "获利了结", "买入", "卖出", "收紧", "stop", "put", "call"])
        vague = any(v in act for v in ["评估", "关注", "密切关注"])
        if vague and not specific:
            errors.append(f"SIGNAL_VAGUE_ACTION: {tid} — {act[:40]}")

    # 3.3 Linked nodes
    for t in triggers:
        tid = t.get("trigger_id", "?")
        if not t.get("linked_nodes"):
            warnings.append(f"SIGNAL_NO_LINK: {tid}")

    # 3.4 Scenario coverage
    scenarios = {"能源/消耗": [], "核升级": [], "停火/降级": [], "EM/金融": []}
    for t in triggers:
        tid = t.get("trigger_id", "?")
        linked = t.get("linked_nodes", [])
        if any(n in linked for n in ["oil_price_100", "hormuz_blockade", "supply_disruption_volume", "energy_crisis"]):
            scenarios["能源/消耗"].append(tid)
        if any(n in linked for n in ["irgc_nuclear"]):
            scenarios["核升级"].append(tid)
        if any(n in linked for n in ["ceasefire_backchannel", "conflict_deescalation"]):
            scenarios["停火/降级"].append(tid)
        if any(n in linked for n in ["em_capital_outflow", "cny_depreciation", "em_debt_crisis", "credit_tightening"]):
            scenarios["EM/金融"].append(tid)

    for scenario, sigs in scenarios.items():
        if not sigs:
            errors.append(f"SIGNAL_BLIND_SPOT: {scenario} 无覆盖")

    # 3.5 Counter-signals (thesis invalidation)
    counter = [t for t in triggers if any(x in t.get("signal", "") for x in ["突降", "SPR", "停火", "阿曼", "瑞士", "降级"])]
    if not counter:
        errors.append("NO_COUNTER_SIGNAL: 只有thesis确认信号，无失效信号")

    # 3.6 Time spectrum
    time_buckets = {"即时": False, "天": False, "周": False}
    for t in triggers:
        lt = t.get("lead_time", "")
        if "即时" in lt:
            time_buckets["即时"] = True
        if "天" in lt:
            time_buckets["天"] = True
        if "周" in lt:
            time_buckets["周"] = True
    for period, covered in time_buckets.items():
        if not covered:
            warnings.append(f"SIGNAL_TIME_GAP: {period}级别无覆盖")

    return errors, warnings, {
        "total_signals": len(triggers),
        "scenarios_covered": {k: len(v) for k, v in scenarios.items()},
        "counter_signals": len(counter),
    }


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    dag = load_dag()
    run = load_run()

    all_errors, all_warnings = [], []

    print("═══ GeoPulse 红队审计 v2 ═══\n")

    # Layer 1
    print("── Layer 1: DAG 结构 ──")
    e1, w1, stats1 = audit_dag_structure(dag)
    all_errors.extend(e1)
    all_warnings.extend(w1)
    print(f"  {stats1['nodes']} nodes / {stats1['edges']} edges / depth {stats1['max_depth']} / leaves {stats1['leaf_pct']:.0%}")
    print(f"  {len(e1)} errors, {len(w1)} warnings")

    # Layer 2
    print("\n── Layer 2: DAG 概率 ──")
    e2, w2, stats2 = audit_dag_probabilities(dag)
    all_errors.extend(e2)
    all_warnings.extend(w2)
    print(f"  prob range: {stats2['prob_min']:.0%} — {stats2['prob_median']:.0%} — {stats2['prob_max']:.0%}")
    print(f"  definitions: {stats2['no_definition']} missing / low_decay: {stats2['low_decay']} / cross_domain: {stats2['cross_domain']}")
    print(f"  {len(e2)} errors, {len(w2)} warnings")

    # Layer 3
    print("\n── Layer 3: 领先信号 ──")
    e3, w3, stats3 = audit_signals(run)
    all_errors.extend(e3)
    all_warnings.extend(w3)
    print(f"  {stats3.get('total_signals', 0)} signals / counter: {stats3.get('counter_signals', 0)}")
    print(f"  coverage: {stats3.get('scenarios_covered', {})}")
    print(f"  {len(e3)} errors, {len(w3)} warnings")

    # Summary
    print(f"\n{'═' * 50}")
    total_e = len(all_errors)
    total_w = len(all_warnings)
    print(f"TOTAL: {total_e} errors, {total_w} warnings")

    if all_errors:
        print("\n❌ ERRORS:")
        for e in all_errors:
            print(f"  {e}")

    if all_warnings and "--verbose" in sys.argv:
        print("\n⚠ WARNINGS:")
        for w in all_warnings:
            print(f"  {w}")

    status = "❌ FAILED" if total_e > 0 else "✅ PASSED"
    print(f"\n{status}")

    return 0 if total_e == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
