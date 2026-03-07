"""
量级→概率delta校准映射。

LLM只输出定性判断(direction + magnitude + likelihood_ratio)。
本模块将定性判断转为定量delta。

校准逻辑:
1. magnitude 决定 delta 的基础范围
2. likelihood_ratio 在范围内精确定位
3. transmission_order 施加衰减
4. confidence 作为 delta 的乘数
"""


# 基础delta范围 (min, mid, max)
MAGNITUDE_RANGES = {
    "negligible": (0.00, 0.01, 0.02),
    "minor":      (0.02, 0.03, 0.05),
    "moderate":   (0.05, 0.07, 0.10),
    "significant":(0.10, 0.12, 0.15),
    "dramatic":   (0.15, 0.20, 0.30),
}

# 似然比 → 在范围内的位置 (0=min, 0.5=mid, 1=max)
LIKELIHOOD_POSITION = {
    "1-2":  0.2,   # 弱证据 → 偏低
    "2-5":  0.5,   # 中等 → 中间
    "5-10": 0.8,   # 强 → 偏高
    ">10":  1.0,   # 极强 → 最大
}

# 传导阶数衰减
ORDER_DECAY = {
    1: 1.0,    # 直接影响，无衰减
    2: 0.60,   # 二阶传导，衰减40%
    3: 0.35,   # 三阶传导，衰减65%
    4: 0.20,   # 四阶传导，衰减80%
}


def calculate_delta(
    magnitude: str,
    likelihood_ratio: str = "2-5",
    transmission_order: int = 1,
    confidence: float = 0.7,
    direction: str = "up",
) -> float:
    """
    从定性判断计算定量概率delta。
    
    Returns:
        float: 概率delta (正=上调, 负=下调)
    """
    # 1. 基础范围
    lo, mid, hi = MAGNITUDE_RANGES.get(magnitude, MAGNITUDE_RANGES["minor"])
    
    # 2. 似然比定位
    pos = LIKELIHOOD_POSITION.get(likelihood_ratio, 0.5)
    base_delta = lo + (hi - lo) * pos
    
    # 3. 传导衰减
    decay = ORDER_DECAY.get(transmission_order, 0.15)
    decayed_delta = base_delta * decay
    
    # 4. 置信度调整
    final_delta = decayed_delta * confidence
    
    # 5. 方向
    if direction == "down":
        final_delta = -final_delta
    elif direction == "unchanged":
        final_delta = 0.0
    
    return round(final_delta, 4)


def apply_impacts(impacts: list[dict], dag: dict) -> dict:
    """
    将P1提取的impacts应用到DAG，返回更新后的DAG。
    
    使用贝叶斯乘法更新而非线性叠加:
    - 同一节点多条evidence: 用odds乘法(避免超100%)
    - P_new = P_old × LR / (P_old × LR + (1 - P_old))
      其中 LR = 似然比（从magnitude和likelihood_ratio推算）
    """
    import copy
    result = copy.deepcopy(dag)
    nodes = result["nodes"]
    changes = []
    
    # 按node_id分组
    from collections import defaultdict
    node_impacts = defaultdict(list)
    for imp in impacts:
        nid = imp.get("node_id", "")
        if nid in nodes and imp.get("direction") != "unchanged":
            node_impacts[nid].append(imp)
    
    for nid, imps in node_impacts.items():
        old_prob = nodes[nid]["probability"]
        prob = old_prob
        
        for imp in imps:
            # 计算等效似然比
            lr = _effective_likelihood_ratio(
                magnitude=imp.get("magnitude", "minor"),
                likelihood_ratio=imp.get("likelihood_ratio", "2-5"),
                transmission_order=imp.get("transmission_order", 1),
                confidence=imp.get("confidence", 0.7),
                direction=imp.get("direction", "up"),
            )
            
            # 贝叶斯更新: P_new = P × LR / (P × LR + (1-P))
            if lr > 0 and 0 < prob < 1:
                odds = prob / (1 - prob)
                new_odds = odds * lr
                prob = new_odds / (1 + new_odds)
        
        prob = round(max(0.01, min(0.99, prob)), 4)  # 永远不到0或1
        
        if abs(prob - old_prob) >= 0.005:
            nodes[nid]["probability"] = prob
            changes.append({
                "node_id": nid,
                "old": old_prob,
                "new": prob,
                "delta": prob - old_prob,
                "n_impacts": len(imps),
            })
    
    return result, changes


# 似然比映射
_LR_BASE = {
    "negligible": 1.05,
    "minor":      1.15,
    "moderate":   1.40,
    "significant":1.80,
    "dramatic":   3.00,
}

_LR_SCALING = {
    "1-2":  0.7,
    "2-5":  1.0,
    "5-10": 1.3,
    ">10":  1.6,
}

def _effective_likelihood_ratio(
    magnitude: str,
    likelihood_ratio: str,
    transmission_order: int,
    confidence: float,
    direction: str,
) -> float:
    """计算等效似然比。"""
    base_lr = _LR_BASE.get(magnitude, 1.15)
    lr_scale = _LR_SCALING.get(likelihood_ratio, 1.0)
    
    # 基础LR
    lr = base_lr ** lr_scale
    
    # 传导衰减: LR向1靠拢
    decay = ORDER_DECAY.get(transmission_order, 0.15)
    lr = 1 + (lr - 1) * decay
    
    # 置信度: LR向1靠拢
    lr = 1 + (lr - 1) * confidence
    
    # 方向: down则取倒数
    if direction == "down":
        lr = 1 / lr
    
    return lr


# ═══════════════════════════════════════════
# Self-test
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=== 校准映射测试 ===\n")
    
    test_cases = [
        ("minor",       "1-2", 1, 0.7, "up"),
        ("minor",       "2-5", 1, 0.7, "up"),
        ("moderate",    "2-5", 1, 0.7, "up"),
        ("moderate",    "5-10",1, 0.8, "up"),
        ("significant", "2-5", 1, 0.8, "up"),
        ("significant", "5-10",1, 0.9, "up"),
        ("significant", ">10", 1, 0.9, "up"),
        ("dramatic",    ">10", 1, 0.9, "up"),
        # 传导衰减
        ("significant", "5-10",1, 0.8, "up"),
        ("significant", "5-10",2, 0.8, "up"),
        ("significant", "5-10",3, 0.8, "up"),
        # 方向
        ("moderate",    "2-5", 1, 0.7, "down"),
    ]
    
    print(f"{'Magnitude':<14} {'LR':>5} {'Ord':>4} {'Conf':>5} {'Dir':>6} → {'Delta':>7}")
    print("-" * 55)
    for mag, lr, order, conf, d in test_cases:
        delta = calculate_delta(mag, lr, order, conf, d)
        print(f"{mag:<14} {lr:>5} {order:>4} {conf:>5.1f} {d:>6} → {delta:>+7.2%}")
