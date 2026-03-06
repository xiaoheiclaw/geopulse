"""Migrate DAG to new node_type + time_horizon schema and clean up noise nodes."""
import json
from datetime import datetime, timezone

dag = json.load(open("data/dag.json"))
nodes = dag["nodes"]
edges = dag["edges"]

# ============================================
# Step 1: Assign node_type and time_horizon
# ============================================

EVENT_NODES = {
    # Confirmed discrete events
    "us_israel_massive_strikes": {},
    "khamenei_assassination": {},
    "iran_massive_retaliation": {},
    "israel_lebanon_invasion": {},
    "qatar_lng_force_majeure": {},
    "us_regime_change_intent": {},
    "us_war_powers_fully_unblocked": {},
    "bahrain_refinery_drone_strike": {},
    "pentagon_war_cost_billions": {},
}

STATE_NODES = {
    # Ongoing conditions — prob = persists next 30d
    "hormuz_blockade_de_facto": {
        "time_horizon": "30d",
        "probability": 0.75,
        "reasoning": "状态节点(30天持续概率)。当前事实：通行量下降80-90%。但美方已承诺护航计划+政治风险保险，伊朗导弹攻击频次下降90%可能降低海峡威胁。30天内完全恢复的概率约25%。"
    },
    "energy_crisis_global": {
        "time_horizon": "30d",
        "probability": 0.8,
        "reasoning": "状态节点(30天持续概率)。三大供应中断(海峡/沙特/卡塔尔)短期内难以同时恢复。但战略储备释放和替代路线正在缓冲。80%概率危机状态持续到4月初。"
    },
    "regional_war_spillover": {
        "time_horizon": "30d",
        "probability": 0.9,
        "reasoning": "状态节点(30天持续概率)。冲突已波及6国，短期内无外交降温机制。持续概率高。"
    },
    "iran_missile_capability_degraded": {
        "label": "伊朗导弹攻击频次下降90%(美方数据)",
        "time_horizon": "30d",
        "probability": 0.7,
        "reasoning": "状态节点(30天持续概率)。B-2打击效果可能持续，但伊朗可能重建机动发射能力或转向其他打击手段。70%概率此状态维持30天。"
    },
    "shipping_insurance_crisis": {
        "time_horizon": "30d",
        "probability": 0.9,
        "reasoning": "状态节点(30天持续概率)。保险公司在战争结束前不会恢复承保。90%概率持续。"
    },
    "kurdish_proxy_war_activated": {
        "time_horizon": "30d",
        "probability": 0.8,
        "reasoning": "状态节点(30天持续概率)。代理人战争一旦启动很难关闭。高持续概率。"
    },
}

PREDICTION_NODES = {
    # Future events with time windows
    "us_iran_ground_war": {
        "time_horizon": "90d",
        "probability": 0.35,
        "reasoning": "预测节点(90天内)。CIA代理人路线降低了大规模地面入侵需求。伊朗面积4倍于伊拉克，后勤成本极高。但若代理人路线失败+regime change僵局，仍可能升级。"
    },
    "oil_price_100_breach": {
        "label": "Brent原油突破$100/桶",
        "time_horizon": "30d",
        "probability": 0.55,
        "reasoning": "预测节点(30天内)。当前$84，距$100约19%。支撑：封锁持续+页岩无法替代。抑制：美方护航+亚洲LNG已回落+战略储备释放。"
    },
    "iran_regime_transition": {
        "time_horizon": "60d",
        "probability": 0.7,
        "reasoning": "预测节点(60天内)。莫杰塔巴继位是最大概率方案，但战时条件下可能推迟正式确认。IRGC可能维持军事委员会过渡。"
    },
    "iran_internal_protests": {
        "label": "伊朗爆发大规模反政府抗议",
        "time_horizon": "30d",
        "probability": 0.5,
        "reasoning": "预测节点(30天内)。存在经济崩溃压力，但外部威胁通常触发rally-around-the-flag效应，短期内可能抑制抗议。互联网封锁也限制了组织能力。"
    },
    "eu_nuclear_plan_b": {
        "label": "法德核保护伞扩展计划取得实质进展",
        "time_horizon": "180d",
        "probability": 0.5,
        "reasoning": "预测节点(180天)。讨论已启动(事实)，但从讨论到实质部署需要漫长的政治协调。6个月内取得实质进展的概率约50%。"
    },
    "trade_route_reshuffle": {
        "time_horizon": "90d",
        "probability": 0.85,
        "reasoning": "预测节点(90天)。重组已在发生(中印→俄油)，但完全固化需要新合同和基础设施。高概率持续。"
    },
    "em_currency_crisis": {
        "label": "新兴市场出现主权债务危机",
        "time_horizon": "90d",
        "probability": 0.4,
        "reasoning": "预测节点(90天)。'危机'=主权违约或资本管制。目前脆弱国家承压但未触发系统性事件。需要油价持续>$100+美元持续走强才会变成真正的危机。"
    },
    "global_stagflation_risk": {
        "label": "全球经济进入滞胀(通胀>4%+GDP增速<1%)",
        "time_horizon": "180d",
        "probability": 0.5,
        "reasoning": "预测节点(180天)。需同时满足通胀上行+增长放缓。若冲突在4-5周内降级，滞胀可能不完全实现。"
    },
    "food_price_surge_global": {
        "time_horizon": "90d",
        "probability": 0.45,
        "reasoning": "预测节点(90天)。天然气→化肥→粮价传导链有2-3个月时滞。当前仅摩尔多瓦初步信号。"
    },
    "fed_policy_dilemma": {
        "label": "美联储被迫在加息抗通胀和降息保增长间做选择",
        "time_horizon": "90d",
        "probability": 0.45,
        "reasoning": "预测节点(90天)。需要冲突长期化(>2个月)且油价持续高位才会迫使美联储表态。若冲突短期结束可继续按兵不动。"
    },
    "turkey_kurdish_tension_risk": {
        "time_horizon": "90d",
        "probability": 0.35,
        "reasoning": "预测节点(90天)。土耳其作为NATO成员不太可能公开对抗美国，但可能通过外交施压或暗中阻挠库尔德行动。"
    },
    "us_shale_cannot_replace": {
        "time_horizon": "30d",
        "probability": 0.95,
        "reasoning": "状态节点(30天)。页岩产能增长受投资周期和基础设施约束，物理上不可能在30天内弥补中东缺口。"
    },
}

# Nodes to DELETE (pure data points or analysis conclusions → merge as evidence)
DELETE_NODES = [
    "gold_record_high",        # → evidence of gold_safe_haven / financial impact
    "usd_dxy_surge",           # → evidence of USD strength
    "sp500_selloff",           # → evidence of equity risk
    "vix_spike",               # → evidence of volatility
    "treasury_selloff_stagflation",  # → evidence of stagflation pricing
    "btc_risk_asset_proven",   # → analysis conclusion, not an event
    "defense_stocks_paradox",  # → evidence of wartime economics
    "polymarket_war_trading",  # → interesting but no downstream causality
    "china_a_share_divergence", # → too speculative, no clear causal role
    "crypto_volatility_spike", # → vague, merge into market impact
    "inflation_expectations_surge", # → evidence of stagflation_risk
    "oil_100_trigger_cascade", # → analysis reasoning, not a discrete node
    "defense_sector_boom",     # → prediction with weak causal links
    "lng_spot_price_surge",    # → merge as evidence of energy_crisis
    "saudi_ras_tanura_hit",    # → merge as evidence of energy crisis
]

# ============================================
# Execute
# ============================================

# Assign types to event nodes
for nid in EVENT_NODES:
    if nid in nodes:
        nodes[nid]["node_type"] = "event"
        nodes[nid]["time_horizon"] = ""

# Assign types and update state nodes
for nid, updates in STATE_NODES.items():
    if nid in nodes:
        nodes[nid]["node_type"] = "state"
        for k, v in updates.items():
            nodes[nid][k] = v

# Assign types and update prediction nodes
for nid, updates in PREDICTION_NODES.items():
    if nid in nodes:
        nodes[nid]["node_type"] = "prediction"
        for k, v in updates.items():
            nodes[nid][k] = v

# Delete noise nodes
for nid in DELETE_NODES:
    nodes.pop(nid, None)

# Clean up edges pointing to/from deleted nodes
valid = set(nodes.keys())
edges = [e for e in edges if e["source"] in valid and e["target"] in valid]

# Ensure no self-loops
edges = [e for e in edges if e["source"] != e["target"]]

# Deduplicate edges
seen = set()
deduped = []
for e in edges:
    key = (e["source"], e["target"])
    if key not in seen:
        seen.add(key)
        deduped.append(e)
edges = deduped

# Any remaining nodes without node_type? Default to "event" for backwards compat
for nid, n in nodes.items():
    if "node_type" not in n:
        n["node_type"] = "event"
    if "time_horizon" not in n:
        n["time_horizon"] = ""

dag["nodes"] = nodes
dag["edges"] = edges
dag["updated"] = datetime.now(timezone.utc).isoformat()

with open("data/dag.json", "w") as f:
    json.dump(dag, f, ensure_ascii=False, indent=2)

# Report
event_count = sum(1 for n in nodes.values() if n.get("node_type") == "event")
state_count = sum(1 for n in nodes.values() if n.get("node_type") == "state")
pred_count = sum(1 for n in nodes.values() if n.get("node_type") == "prediction")

print(f"=== DAG 清洗完成 ===")
print(f"删除: {len(DELETE_NODES)} 个噪音节点")
print(f"剩余: {len(nodes)} 节点, {len(edges)} 边")
print(f"  事件: {event_count} | 状态: {state_count} | 预测: {pred_count}")
print()
for nid, n in sorted(nodes.items(), key=lambda x: (-x[1]["probability"])):
    tag = n.get("node_type", "?")[:4]
    th = n.get("time_horizon", "")
    th_str = f" [{th}]" if th else ""
    print(f"  [{tag}] {n['probability']:.2f}{th_str} | {n['label']}")
