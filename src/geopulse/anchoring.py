"""
基础概率锚定方法。

三种方法，按优先级:
1. 市场隐含 — 有金融数据的节点直接从市场价格反推
2. 分解法 — 大概率拆成小概率的乘积
3. 参考类 — 历史上类似情况的基础率 + 调整因子

所有基础概率必须标注来源方法。
"""

# 市场隐含概率的计算
from math import log, sqrt, exp
from scipy.stats import norm  # type: ignore


def implied_prob_from_option(
    spot: float,
    strike: float,
    iv: float,
    days: int = 30,
    rate: float = 0.04,
) -> float:
    """
    从期权隐含波动率估算标的超过strike的概率。
    简化Black-Scholes: P(S > K) ≈ N(d2)
    """
    t = days / 365
    d2 = (log(spot / strike) + (rate - 0.5 * iv**2) * t) / (iv * sqrt(t))
    return round(norm.cdf(d2), 4)


def implied_prob_from_drawdown(
    vix: float,
    drawdown_pct: float = 0.05,
    days: int = 30,
) -> float:
    """
    从VIX估算S&P在N天内下跌>X%的概率。
    VIX = 年化隐含波动率 × 100
    """
    annual_vol = vix / 100
    daily_vol = annual_vol / sqrt(252)
    period_vol = daily_vol * sqrt(days)
    z = -drawdown_pct / period_vol  # 负方向
    return round(norm.cdf(z), 4)


# 分解法
def decompose_prob(*sub_probs: float) -> float:
    """
    P(A) = P(B) × P(C|B) × P(D|C)
    输入各子概率，返回联合概率。
    """
    result = 1.0
    for p in sub_probs:
        result *= p
    return round(result, 4)


# 参考类
def reference_class_adjust(
    base_rate: float,
    adjustments: list[tuple[str, float]],
) -> float:
    """
    从参考类基础率出发，用似然比调整。
    
    adjustments: [(reason, likelihood_ratio), ...]
    """
    odds = base_rate / (1 - base_rate) if base_rate < 1 else 99
    for reason, lr in adjustments:
        odds *= lr
    prob = odds / (1 + odds)
    return round(max(0.01, min(0.99, prob)), 4)


# ═══════════════════════════════════════════
# 当前DAG节点的锚定审计
# ═══════════════════════════════════════════

ANCHORING_AUDIT = {
    # 市场隐含
    "oil_price_100": {
        "method": "market_implied",
        "calculation": "Brent spot $92.69, OVX=103.6 → IV≈104%, 30d P(>$100) ≈ implied_prob_from_option(92.69, 100, 1.04, 30)",
        "note": "可直接从Brent $100 call option定价",
    },
    "equity_correction": {
        "method": "market_implied",
        "calculation": "VIX=29.5 → implied_prob_from_drawdown(29.5, 0.05, 30)",
        "note": "从VIX直接算S&P -5%概率",
    },
    
    # 分解法
    "energy_crisis": {
        "method": "decomposition",
        "calculation": "P(封锁持续) × P(封锁→缺口>3mbpd) × P(缺口→IEA紧急状态) = 0.90 × 0.85 × 0.90 = 0.69",
        "note": "三个子概率都比直接猜整体概率容易判断",
    },
    "global_stagflation": {
        "method": "decomposition",
        "calculation": "P(油价>$100持续>4周) × P(→CPI>4%) × P(→GDP<1%) = 0.72 × 0.75 × 0.65 = 0.35",
        "note": "当前DAG给45%，可能偏高",
    },
    
    # 参考类
    "hormuz_blockade": {
        "method": "reference_class",
        "base_rate": 0.25,  # 历史4次严重对峙中1次有效封锁
        "adjustments": [
            ("美以已空袭伊朗本土(史无前例)", 3.0),
            ("哈梅内伊被杀(政权存亡危机)", 2.5),
            ("IRGC常规能力被削弱90%", 0.8),  # 封锁也需要军事能力
        ],
        "note": "参考类基础率25%，经3个调整因子后≈82%",
    },
    "ceasefire_backchannel": {
        "method": "reference_class",
        "base_rate": 0.60,  # 历史上大多数战争最终都停火
        "adjustments": [
            ("无条件投降要求(极端立场)", 0.15),
            ("俄罗斯军事介入(调停方消失)", 0.5),
            ("战争仅8天(太早谈停火)", 0.7),
        ],
        "note": "基础率60%经大幅下调后≈7%",
    },
}


if __name__ == "__main__":
    print("=== 市场隐含概率 ===\n")
    
    # Brent > $100
    p_brent = implied_prob_from_option(92.69, 100, 1.04, 30)
    print(f"P(Brent > $100 in 30d): {p_brent:.1%}")
    print(f"  (spot=$92.69, IV=104%, 30天)")
    
    # S&P drawdown > 5%
    p_sp = implied_prob_from_drawdown(29.5, 0.05, 30)
    print(f"\nP(S&P下跌>5% in 30d): {p_sp:.1%}")
    print(f"  (VIX=29.5)")
    
    print("\n=== 分解法 ===\n")
    p_crisis = decompose_prob(0.90, 0.85, 0.90)
    print(f"P(能源危机) = 0.90 × 0.85 × 0.90 = {p_crisis:.1%}")
    print(f"  (DAG当前: 72%)")
    
    p_stag = decompose_prob(0.72, 0.75, 0.65)
    print(f"P(滞胀) = 0.72 × 0.75 × 0.65 = {p_stag:.1%}")
    print(f"  (DAG当前: 45%)")
    
    print("\n=== 参考类 ===\n")
    p_block = reference_class_adjust(0.25, [
        ("空袭伊朗本土", 3.0),
        ("哈梅内伊被杀", 2.5),
        ("IRGC削弱90%", 0.8),
    ])
    print(f"P(霍尔木兹封锁) = ref_class(25%) + 3个调整 = {p_block:.1%}")
    print(f"  (DAG当前: 90%)")
    
    p_cease = reference_class_adjust(0.60, [
        ("无条件投降要求", 0.15),
        ("俄罗斯军事介入", 0.5),
        ("战争仅8天", 0.7),
    ])
    print(f"P(停火谈判) = ref_class(60%) + 3个调整 = {p_cease:.1%}")
    print(f"  (DAG当前: 12%)")
