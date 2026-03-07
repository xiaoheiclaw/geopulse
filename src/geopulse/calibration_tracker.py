"""
预测校准系统。

记录每个概率预测，等结果出来后计算准确度。
用 Brier Score 分解找出哪里系统性偏了。
"""

import json
import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
LEDGER_PATH = DATA_DIR / "prediction_ledger.json"


def _load_ledger() -> list[dict]:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return []


def _save_ledger(ledger: list[dict]):
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))


def record_prediction(
    node_id: str,
    label: str,
    probability: float,
    method: str,
    resolve_by: str,          # ISO date: 什么时候能验证
    resolution_criteria: str, # 怎么判断对错
    dag_version: int = 0,
    notes: str = "",
) -> dict:
    """
    记录一条预测。
    
    每次DAG更新时自动调用，把关键节点的概率快照存下来。
    """
    ledger = _load_ledger()
    
    entry = {
        "id": f"{node_id}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}",
        "node_id": node_id,
        "label": label,
        "probability": probability,
        "method": method,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "resolve_by": resolve_by,
        "resolution_criteria": resolution_criteria,
        "dag_version": dag_version,
        "notes": notes,
        # 结果（等事件发生后填）
        "outcome": None,       # 1.0(发生) 或 0.0(没发生)
        "resolved_at": None,
        "brier": None,
    }
    
    ledger.append(entry)
    _save_ledger(ledger)
    return entry


def resolve_prediction(prediction_id: str, outcome: float):
    """
    填入结果: 1.0=发生, 0.0=没发生, 0.5=部分/模糊
    """
    ledger = _load_ledger()
    
    for entry in ledger:
        if entry["id"] == prediction_id:
            entry["outcome"] = outcome
            entry["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            entry["brier"] = (entry["probability"] - outcome) ** 2
            _save_ledger(ledger)
            return entry
    
    raise ValueError(f"Prediction {prediction_id} not found")


def calibration_report() -> dict:
    """
    生成校准报告。
    
    输出:
    - overall_brier: 总Brier分数 (0=完美, 0.25=随机)
    - calibration_curve: 按概率区间的实际频率 (理想=对角线)
    - by_method: 每种方法的Brier分数
    - by_node: 每个节点的Brier分数
    - bias: 系统性偏差方向
    """
    ledger = _load_ledger()
    resolved = [e for e in ledger if e["outcome"] is not None]
    
    if not resolved:
        return {"status": "no_resolved_predictions", "total": len(ledger), "pending": len(ledger)}
    
    # 总Brier
    briers = [e["brier"] for e in resolved]
    overall = sum(briers) / len(briers)
    
    # 校准曲线: 按概率区间分桶
    bins = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    calibration = []
    for lo, hi in bins:
        bucket = [e for e in resolved if lo <= e["probability"] < hi]
        if bucket:
            avg_prob = sum(e["probability"] for e in bucket) / len(bucket)
            avg_outcome = sum(e["outcome"] for e in bucket) / len(bucket)
            calibration.append({
                "range": f"{lo:.0%}-{hi:.0%}",
                "count": len(bucket),
                "avg_predicted": round(avg_prob, 3),
                "avg_actual": round(avg_outcome, 3),
                "gap": round(avg_prob - avg_outcome, 3),
            })
    
    # 按方法
    methods = {}
    for e in resolved:
        m = e.get("method", "unknown")
        if m not in methods:
            methods[m] = []
        methods[m].append(e["brier"])
    by_method = {m: round(sum(bs)/len(bs), 4) for m, bs in methods.items()}
    
    # 按节点
    nodes = {}
    for e in resolved:
        n = e["node_id"]
        if n not in nodes:
            nodes[n] = []
        nodes[n].append(e["brier"])
    by_node = {n: round(sum(bs)/len(bs), 4) for n, bs in nodes.items()}
    
    # 偏差检测
    avg_pred = sum(e["probability"] for e in resolved) / len(resolved)
    avg_outcome = sum(e["outcome"] for e in resolved) / len(resolved)
    bias = avg_pred - avg_outcome
    
    return {
        "status": "ok",
        "total_predictions": len(ledger),
        "resolved": len(resolved),
        "pending": len(ledger) - len(resolved),
        "overall_brier": round(overall, 4),
        "brier_interpretation": (
            "excellent" if overall < 0.05 else
            "good" if overall < 0.10 else
            "fair" if overall < 0.15 else
            "mediocre" if overall < 0.20 else
            "poor"
        ),
        "calibration_curve": calibration,
        "by_method": by_method,
        "by_node": by_node,
        "bias": round(bias, 4),
        "bias_direction": "overconfident" if bias > 0.05 else "underconfident" if bias < -0.05 else "neutral",
    }


def snapshot_dag(dag: dict):
    """
    DAG更新时自动快照关键节点。
    """
    key_nodes = [
        "oil_price_100", "hormuz_blockade", "equity_correction",
        "energy_crisis", "global_stagflation", "conflict_protracted",
        "ceasefire", "em_debt_crisis", "safe_haven_rally", "cyber_attack",
    ]
    
    version = dag.get("version", 0)
    
    for nid in key_nodes:
        if nid not in dag.get("nodes", {}):
            continue
        node = dag["nodes"][nid]
        prob = node.get("probability", 0)
        
        # 从falsification拿resolve_by
        fc = node.get("falsification", {})
        resolve_by = fc.get("deadline", "2026-06-01")
        criteria = fc.get("criteria", f"{node.get('label', nid)} 是否发生")
        method = node.get("probability_method", "expert_judgment")
        
        record_prediction(
            node_id=nid,
            label=node.get("label", nid),
            probability=prob,
            method=method,
            resolve_by=resolve_by,
            resolution_criteria=criteria,
            dag_version=version,
        )


if __name__ == "__main__":
    # 把当前DAG快照一次
    dag = json.loads((DATA_DIR / "dag.json").read_text())
    snapshot_dag(dag)
    
    ledger = _load_ledger()
    print(f"✅ 预测账本: {len(ledger)} 条记录")
    print(f"\n最新快照 (DAG v{dag.get('version', '?')}):")
    for e in ledger[-10:]:
        print(f"  {e['label'][:30]:<32} P={e['probability']:.0%}  resolve_by={e['resolve_by'][:10]}")
    
    print(f"\n校准报告:")
    report = calibration_report()
    print(f"  状态: {report['status']}")
    print(f"  总记录: {report.get('total_predictions', report.get('total', '?'))}, 待验证: {report.get('pending', '?')}")


# ═══════════════════════════════════════════
# 闭环: 校准结果 → 参数调整
# ═══════════════════════════════════════════

def auto_adjust(min_resolved: int = 10) -> dict | None:
    """
    从校准结果自动调整系统参数。
    
    需要至少 min_resolved 条已验证预测才启动。
    
    调整逻辑:
    1. 整体偏差 → 调整全局 shrinkage factor
    2. 按方法偏差 → 调整 METHOD_PRIORITY 权重
    3. 按概率区间偏差 → 调整特定区间的 base rate
    """
    report = calibration_report()
    
    if report["status"] != "ok" or report["resolved"] < min_resolved:
        return {
            "status": "insufficient_data",
            "resolved": report.get("resolved", 0),
            "needed": min_resolved,
            "message": f"需要{min_resolved}条已验证预测，当前{report.get('resolved', 0)}条",
        }
    
    adjustments = []
    
    # ── 1. 整体偏差 → shrinkage ──
    bias = report["bias"]
    if abs(bias) > 0.05:
        # 我们系统性偏高/偏低
        # shrinkage: 所有新概率向50%收缩 bias量
        shrinkage = round(min(0.15, abs(bias)), 3)
        direction = "toward_50" if bias > 0 else "away_from_50"
        adjustments.append({
            "type": "global_shrinkage",
            "bias": bias,
            "shrinkage_factor": shrinkage,
            "direction": direction,
            "action": f"所有新概率向50%{'收缩' if bias > 0 else '推离'}{shrinkage:.1%}",
            "reason": f"系统{'高估' if bias > 0 else '低估'}偏差={bias:.1%}",
        })
    
    # ── 2. 按方法偏差 → 权重调整 ──
    from geopulse.calibration import METHOD_PRIORITY
    
    method_briers = report.get("by_method", {})
    if len(method_briers) >= 2:
        best = min(method_briers, key=method_briers.get)
        worst = max(method_briers, key=method_briers.get)
        
        if method_briers[worst] > method_briers[best] * 2:
            # 最差方法Brier是最好的2倍以上 → 降权
            old_w = METHOD_PRIORITY.get(worst, 0.5)
            new_w = round(max(0.1, old_w * 0.7), 2)  # 降30%
            adjustments.append({
                "type": "method_reweight",
                "worst_method": worst,
                "worst_brier": method_briers[worst],
                "best_method": best,
                "best_brier": method_briers[best],
                "old_weight": old_w,
                "new_weight": new_w,
                "action": f"METHOD_PRIORITY['{worst}'] {old_w}→{new_w}",
                "reason": f"{worst}的Brier({method_briers[worst]:.3f})是{best}({method_briers[best]:.3f})的{method_briers[worst]/method_briers[best]:.1f}倍",
            })
    
    # ── 3. 按区间偏差 → 校准曲线修正 ──
    for bucket in report.get("calibration_curve", []):
        gap = bucket["gap"]  # predicted - actual
        if abs(gap) > 0.10 and bucket["count"] >= 3:
            adjustments.append({
                "type": "bucket_correction",
                "range": bucket["range"],
                "predicted_avg": bucket["avg_predicted"],
                "actual_avg": bucket["avg_actual"],
                "gap": gap,
                "count": bucket["count"],
                "action": f"[{bucket['range']}]区间的概率偏{'高' if gap > 0 else '低'}{abs(gap):.0%}",
                "reason": f"预测{bucket['avg_predicted']:.0%} vs 实际{bucket['avg_actual']:.0%} (n={bucket['count']})",
            })
    
    result = {
        "status": "adjustments_ready",
        "resolved": report["resolved"],
        "overall_brier": report["overall_brier"],
        "bias": report["bias"],
        "adjustments": adjustments,
        "auto_apply": False,  # 需要人工确认
    }
    
    return result


def apply_shrinkage(probability: float, shrinkage: float) -> float:
    """
    向50%收缩。
    
    shrinkage=0.10 means: 新概率 = 原概率×0.90 + 0.50×0.10
    """
    return round(probability * (1 - shrinkage) + 0.5 * shrinkage, 4)
