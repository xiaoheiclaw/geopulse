"""
条件价格模型 — 从供需基本面推导，不拍脑袋。

核心原则:
1. 条件价格是时间曲线，不是单个数字
2. 供给曲线是凸的（接近满产边际成本急升）
3. 需求弹性按时间框架递增（短期刚性→中期崩塌）
4. 恐慌溢价有半衰期（~4周减半）
5. 每个参数标注来源

数据来源:
- IEA Monthly Oil Market Report (Feb 2026)
- EIA Short-Term Energy Outlook (Mar 2026)
- IMF WEO demand elasticity estimates
- 历史恐慌溢价: 1990海湾/2008格鲁吉亚/2019沙特/2022俄乌
"""

PRE_CONFLICT_BRENT = 68.6  # $/bbl, 2/28收盘
GLOBAL_DEMAND = 103.5       # mbpd (IEA Feb 2026)

# 供给参数 (来源: IEA/OPEC MOMR)
IRAN_EXPORTS = 1.5          # mbpd (制裁下)
HORMUZ_TRANSIT = 17.0       # mbpd
OPEC_SPARE = 3.0            # mbpd (沙特+阿联酋)
SPR_MAX_RATE = 1.0          # mbpd (美国历史最高释放速率)
IEA_COORDINATED = 1.5       # mbpd (IEA成员协调释放)

# 供给曲线: 凸函数
# 参考: 2008年 ~2mbpd缺口 → Brent +$57
def supply_premium(net_gap_mbpd: float) -> float:
    """二次供给曲线: premium = 5*gap² + 7*gap"""
    if net_gap_mbpd <= 0:
        return 0.0
    return 5 * net_gap_mbpd**2 + 7 * net_gap_mbpd

# 需求弹性 (来源: IMF WEO, Hamilton 2009)
# 短期几乎零弹性，中期逐步增大
ELASTICITY_BY_WEEK = {
    1: -0.01,   # Week 1: 刚性需求
    2: -0.02,   # Week 2
    4: -0.04,   # Month 1: 短途出行减少
    8: -0.07,   # Month 2: 工业减产
    12: -0.12,  # Month 3: 结构性需求崩塌
    24: -0.20,  # Month 6: 衰退
}

# 恐慌溢价 (来源: 历史事件校准)
PANIC_PREMIUM_PCT = {
    "low":     0.05,   # ~2008格鲁吉亚
    "medium":  0.15,   # ~2022俄乌早期
    "high":    0.35,   # ~1990海湾
    "extreme": 0.55,   # 无历史先例
}
PANIC_HALF_LIFE_WEEKS = 4  # 恐慌溢价半衰期


def get_elasticity(week: int) -> float:
    keys = sorted(ELASTICITY_BY_WEEK.keys())
    e = ELASTICITY_BY_WEEK[keys[0]]
    for k in keys:
        if week >= k:
            e = ELASTICITY_BY_WEEK[k]
    return e


def calc_brent(
    supply_loss: float,
    offset: float,
    panic_level: str,
    week: int,
) -> dict:
    """
    从供需缺口计算均衡Brent价格。
    
    supply_loss: 供应损失 (mbpd)
    offset: 对冲量 (OPEC补产+SPR+IEA) (mbpd)
    panic_level: low/medium/high/extreme
    week: 冲突第几周
    """
    net_gap = supply_loss - offset
    elasticity = get_elasticity(week)
    
    # 供给溢价
    s_prem = supply_premium(max(0, net_gap))
    
    # 恐慌溢价 (半衰期衰减)
    panic_base = PANIC_PREMIUM_PCT.get(panic_level, 0) * PRE_CONFLICT_BRENT
    panic_prem = panic_base * (0.5 ** (max(0, week - 1) / PANIC_HALF_LIFE_WEEKS))
    
    # 初始价格
    price_raw = PRE_CONFLICT_BRENT + s_prem + panic_prem
    
    # 需求反馈
    price_pct_change = (price_raw - PRE_CONFLICT_BRENT) / PRE_CONFLICT_BRENT
    demand_reduction = GLOBAL_DEMAND * abs(elasticity) * price_pct_change
    
    # 调整后缺口
    adjusted_gap = net_gap - demand_reduction
    s_prem_adj = supply_premium(max(0, adjusted_gap))
    price_final = PRE_CONFLICT_BRENT + s_prem_adj + panic_prem
    
    return {
        "price": round(price_final, 1),
        "net_gap_mbpd": round(net_gap, 2),
        "gap_after_demand_mbpd": round(adjusted_gap, 2),
        "supply_premium": round(s_prem_adj, 1),
        "panic_premium": round(panic_prem, 1),
        "demand_reduction_mbpd": round(demand_reduction, 2),
        "elasticity": elasticity,
    }


def implied_blockade_prob(
    current_brent: float,
    blockade_price: float,
    no_blockade_price: float,
) -> float:
    """
    从当前Brent反推市场隐含封锁概率。
    P = (current - no_blockade) / (blockade - no_blockade)
    """
    if blockade_price == no_blockade_price:
        return 0.5
    p = (current_brent - no_blockade_price) / (blockade_price - no_blockade_price)
    return round(max(0.0, min(1.0, p)), 4)
