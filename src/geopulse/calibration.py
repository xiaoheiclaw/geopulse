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


# ═══════════════════════════════════════════
# P4/P2/P6 偏离程度→调整量映射
# ═══════════════════════════════════════════

# 红队/场景评估的偏离程度 → 建议调整的似然比
DEVIATION_LR = {
    "fair": 1.0,           # 不调
    "slight": 1.20,        # 小幅调整
    "moderate": 1.50,      # 中等调整
    "strong": 2.00,        # 大幅调整
}


def apply_deviation(
    current_prob: float,
    assessment: str,       # "overestimated" | "underestimated" | "fair"
    deviation: str = "moderate",  # "slight" | "moderate" | "strong"
) -> float:
    """
    根据红队的定性偏离判断计算调整后概率。
    
    overestimated → 下调 (LR < 1)
    underestimated → 上调 (LR > 1)
    fair → 不变
    """
    lr = DEVIATION_LR.get(deviation, 1.0)
    
    if assessment == "overestimated":
        lr = 1 / lr  # 取倒数 → 下调
    elif assessment == "fair":
        return current_prob
    # underestimated: lr > 1 → 上调
    
    if 0 < current_prob < 1:
        odds = current_prob / (1 - current_prob)
        new_odds = odds * lr
        new_prob = new_odds / (1 + new_odds)
        return round(max(0.01, min(0.99, new_prob)), 4)
    
    return current_prob


# ═══════════════════════════════════════════
# 多方法聚合规则
# ═══════════════════════════════════════════

METHOD_PRIORITY = {
    "market_implied": 1.0,     # 有真金白银做后盾
    "supply_demand_model": 0.9,
    "decomposition": 0.7,      # 结构工具，子概率质量决定总质量
    "reference_class": 0.6,    # 样本小，调整因子主观
    "expert_judgment": 0.4,    # 最后手段
}


def aggregate_methods(
    estimates: list[dict],
) -> dict:
    """
    多方法冲突时的聚合规则。
    
    estimates: [{"method": "market_implied", "value": 0.39, "range": [0.30, 0.55]}, ...]
    
    规则:
    1. 如果只有一种方法 → 直接用
    2. 如果区间有重叠 → 取重叠区间的加权中点
    3. 如果区间无重叠 → 用方法优先级加权平均，但标记 FLAG
    """
    if len(estimates) == 1:
        e = estimates[0]
        return {"value": e["value"], "range": e["range"], "conflict": False}
    
    # 按优先级排序
    for e in estimates:
        e["weight"] = METHOD_PRIORITY.get(e["method"], 0.5)
    
    # 检查区间重叠
    lo = max(e["range"][0] for e in estimates)
    hi = min(e["range"][1] for e in estimates)
    overlap = lo <= hi
    
    if overlap:
        # 重叠区间内的加权中点
        total_w = sum(e["weight"] for e in estimates)
        weighted_val = sum(e["value"] * e["weight"] for e in estimates) / total_w
        # 钳制到重叠区间
        final = max(lo, min(hi, weighted_val))
        return {
            "value": round(final, 3),
            "range": [round(lo, 3), round(hi, 3)],
            "conflict": False,
            "note": f"区间重叠[{lo:.0%},{hi:.0%}], 加权中点",
        }
    else:
        # 无重叠 → FLAG
        total_w = sum(e["weight"] for e in estimates)
        weighted_val = sum(e["value"] * e["weight"] for e in estimates) / total_w
        full_lo = min(e["range"][0] for e in estimates)
        full_hi = max(e["range"][1] for e in estimates)
        return {
            "value": round(weighted_val, 3),
            "range": [round(full_lo, 3), round(full_hi, 3)],
            "conflict": True,
            "flag": f"⚠️ 方法冲突: 区间不重叠, 加权平均{weighted_val:.0%}, 高优先级方法偏向{estimates[0]['method']}",
        }


# ═══════════════════════════════════════════
# 时间累积/衰减模型
# ═══════════════════════════════════════════

import math

def time_adjusted_prob(
    base_prob: float,
    days_elapsed: int,
    window_days: int,
    pattern: str = "front_loaded",
) -> float:
    """
    节点概率的时间调整。
    
    pattern:
    - "front_loaded": 早期更可能发生(如军事突袭)
        → 没发生的每一天都降低概率
    - "cumulative": 随时间累积(如需求崩塌)
        → 时间越长概率越高
    - "window": 有特定窗口(如选举前)
        → 窗口外概率骤降
    
    返回: 在第days_elapsed天的条件概率
    """
    t = days_elapsed / window_days  # 归一化时间 [0, 1+]
    
    if pattern == "front_loaded":
        # 如果window_days内没发生，概率按指数衰减
        # 逻辑: 如果会发生，大概率在前期
        if t >= 1.0:
            # 窗口已过，大幅衰减
            return round(base_prob * 0.3, 4)
        # 窗口内: 条件概率 = base * (1 - t^0.5)的某种形式
        # 更直觉: 已经过了t%的窗口没发生 → 后验下调
        survival = 1 - t  # 剩余窗口比例
        # 贝叶斯: P(最终发生|前t没发生) 取决于发生时间分布
        # 假设均匀分布: P = base * survival / (1 - base + base*survival)
        conditional = base_prob * survival / (1 - base_prob + base_prob * survival)
        return round(max(0.01, conditional), 4)
    
    elif pattern == "cumulative":
        # 随时间累积——越久越可能
        # 1 - (1-daily_rate)^days, daily_rate从base_prob反推
        if window_days <= 0:
            return base_prob
        daily_rate = 1 - (1 - base_prob) ** (1 / window_days)
        cumulative = 1 - (1 - daily_rate) ** days_elapsed
        return round(max(0.01, min(0.99, cumulative)), 4)
    
    elif pattern == "window":
        # 窗口型: 窗口前概率上升，窗口后骤降
        if t > 1.2:
            return round(base_prob * 0.1, 4)  # 窗口过后大幅下降
        elif t > 0.8:
            return round(min(0.99, base_prob * 1.2), 4)  # 临近窗口峰值
        else:
            return round(base_prob * (0.5 + 0.5 * t / 0.8), 4)  # 逐步上升
    
    return base_prob


# ═══════════════════════════════════════════
# 似然比相关性修正
# ═══════════════════════════════════════════

def correlated_lr_adjust(
    likelihood_ratios: list[tuple[str, float]],
    correlations: dict[tuple[str, str], float] | None = None,
) -> float:
    """
    修正似然比连乘的独立性假设。
    
    likelihood_ratios: [(name, lr), ...]
    correlations: {(name1, name2): rho, ...}  rho ∈ [0, 1]
    
    如果两个因子相关(rho>0)，第二个因子的LR向1衰减:
    effective_lr2 = 1 + (lr2 - 1) * (1 - rho)
    """
    if not correlations:
        # 无相关性信息 → 直接乘（原始行为）
        result = 1.0
        for _, lr in likelihood_ratios:
            result *= lr
        return round(result, 4)
    
    # 按顺序应用，考虑相关性衰减
    applied = []
    result = 1.0
    
    for name, lr in likelihood_ratios:
        max_rho = 0.0
        for prev_name in applied:
            key = (prev_name, name) if (prev_name, name) in correlations else (name, prev_name)
            if key in correlations:
                max_rho = max(max_rho, correlations[key])
        
        effective_lr = 1 + (lr - 1) * (1 - max_rho)
        result *= effective_lr
        applied.append(name)
    
    return round(result, 4)


# ═══════════════════════════════════════════
# ρ 估计指南 (红队终审条件)
# ═══════════════════════════════════════════

RHO_DEFAULTS = {
    "same_action":      0.90,  # 同一行动的不同结果 (空袭→领导人被杀)
    "same_causal_chain": 0.70, # 同一因果链上的节点 (封锁→中断→缺口)
    "same_domain":      0.50,  # 同一领域但不同链 (两个能源事件)
    "cross_domain":     0.20,  # 跨领域 (军事→金融)
    "independent":      0.00,  # 确认无关
}

# 使用规则:
# 1. 默认 ρ=0.50 (same_domain)
# 2. 同因果链 ρ≥0.70, 同行动 ρ≥0.90
# 3. 跨领域 ρ=0.20 除非有明确传导机制
# 4. 每次使用非默认ρ需记录理由
# 5. 敏感性检查: ρ±0.15 对结论有影响时标记 FLAG
