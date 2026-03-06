"""Red Team审计：对DAG中每个节点进行严格拷问"""
import json
from datetime import datetime, timezone

dag = json.load(open("data/dag.json"))
nodes = dag["nodes"]
edges = dag["edges"]

# ==========================================
# 问题清单 & 修复方案
# ==========================================

# --- 问题1: 重复节点 ---
# khamenei_assassination vs khamenei_assassinated (完全相同的事件)
# iran_massive_retaliation vs iran_mass_retaliation_missiles (同一事件)
# iran_regime_transition vs mojtaba_khamenei_succession (同一事件)
# iran_internal_protests vs iran_1979_scale_protests (同一事件)
# energy_crisis_global vs global_energy_crisis_imminent (同一概念)
# gold_safe_haven_rally vs gold_record_high (重叠)
# usd_strength_surge vs usd_dxy_surge (重叠)
# global_equity_selloff vs sp500_selloff (高度重叠)

DUPLICATES_TO_REMOVE = [
    "khamenei_assassinated",        # 保留 khamenei_assassination
    "iran_mass_retaliation_missiles", # 保留 iran_massive_retaliation
    "mojtaba_khamenei_succession",   # 保留 iran_regime_transition
    "iran_1979_scale_protests",      # 保留 iran_internal_protests
    "global_energy_crisis_imminent", # 保留 energy_crisis_global
    "gold_safe_haven_rally",         # 保留 gold_record_high (有实际数据)
    "usd_strength_surge",            # 保留 usd_dxy_surge (有实际数据)
    "global_equity_selloff",         # 保留 sp500_selloff (有实际数据)
]

# --- 问题2: 已发生事件的概率不是1.0 ---
FACT_NODES_FIX = {
    "iran_massive_retaliation": {
        "probability": 1.0,
        "reasoning": "已发生事实：伊朗于3月1日起对以色列、美军基地及6个海湾国家发射500+弹道导弹和2000+无人机。"
    },
    "hormuz_blockade_de_facto": {
        "probability": 0.95,  # 这个有争议：伊朗海军副司令称并未正式封锁
        "reasoning": "事实上的封锁（非法律意义）：通行量下降80-90%，保险公司撤离，200+船滞留。但伊朗官方否认正式封锁，美方提出护航计划，存在部分恢复可能。"
    },
    "regional_war_spillover": {
        "probability": 1.0,
        "reasoning": "已发生事实：伊朗导弹/无人机打击波及迪拜、阿布扎比、巴林、科威特、卡塔尔、阿曼6国。"
    },
    "israel_lebanon_invasion": {
        "probability": 1.0,
        "confidence": 1.0,
        "reasoning": "已发生事实：以色列3月3日授权地面入侵，命令20万居民撤离，部队已越境进入南黎巴嫩。"
    },
    "iran_internal_protests": {
        "probability": 0.85,
        "confidence": 0.7,
        "reasoning": "部分发生：有大规模抗议报道，但'1979级别'的定性缺乏独立验证。伊朗已封锁互联网，外部信息受限。概率反映抗议存在但规模不确定。"
    },
    "gold_record_high": {
        "probability": 1.0,
        "reasoning": "已发生事实：3月5日黄金触及$5,183/oz历史新高。CNBC、FXStreet多源确认。"
    },
    "usd_dxy_surge": {
        "probability": 1.0,
        "reasoning": "已发生事实：DXY于3月5日升至99.1，创2022年来最佳周表现。TradingEconomics确认。"
    },
    "sp500_selloff": {
        "probability": 1.0,
        "reasoning": "已发生事实：3月5日S&P 500跌0.56%至6830.71，道指跌784点(-1.61%)。CNBC/CNN多源确认。"
    },
    "vix_spike": {
        "probability": 1.0,
        "reasoning": "已发生事实：VIX从战前水平升至23.57(3月3日)，CNN确认单日飙升11%。"
    },
    "treasury_selloff_stagflation": {
        "probability": 1.0,
        "reasoning": "已发生事实：10Y收益率从战前<4%升至4.09%。这是滞胀定价——油价冲击带来的通胀预期上行力量压制了地缘避险买盘(Deutsche Bank: no signs of safe haven demand)。"
    },
    "btc_risk_asset_proven": {
        "probability": 1.0,
        "reasoning": "已发生事实：BTC在战争爆发后跌破$66K，后反弹至$68.9K。Euronews确认加密资产作为风险资产代理被抛售。'数字黄金'叙事在本次地缘危机中未获验证。"
    },
    "defense_stocks_paradox": {
        "probability": 1.0,
        "reasoning": "已发生事实：LMT/RTX/BA均下跌2-3%。原因不是战争利空军工，而是特朗普政府限制军工企业回购以强制扩产——'战时经济学'回归(FinancialContent确认)。"
    },
    "pentagon_war_cost_billions": {
        "probability": 1.0,
        "reasoning": "已发生事实：The Cradle报道五角大楼4天内消耗年度预算的0.1%(约$50亿+)，专家估计3周战争可能花费数百亿。"
    },
    "saudi_ras_tanura_hit": {
        "probability": 1.0,
        "reasoning": "已发生事实：沙特Ras Tanura炼油厂(日处理55万桶)被伊朗无人机击中起火后关停。GMF市场追踪确认。"
    },
    "shipping_insurance_crisis": {
        "probability": 1.0,
        "confidence": 0.95,
        "reasoning": "已发生事实：保险公司取消霍尔木兹海峡战争险，VLCC运费创纪录$423,736/天。航运巨头暂停穿越。"
    },
    "polymarket_war_trading": {
        "probability": 1.0,
        "reasoning": "已发生事实：Polymarket用户在伊朗打击头寸上获利$500K+。美参议员已提出禁止政府官员参与预测市场交易的法案。"
    },
}

# --- 问题3: 概率/推理需要修正的预测节点 ---
PREDICTION_FIXES = {
    "us_iran_ground_war": {
        "probability": 0.45,
        "confidence": 0.6,
        "reasoning": "预测节点。特朗普口头不排除，但实际军事逻辑约束很强：伊朗面积是伊拉克的4倍，地形复杂(扎格罗斯山脉)，美军在阿富汗/伊拉克的教训犹在。参院否决战争权力限制消除了法律障碍，但后勤和政治成本极高。CIA武装库尔德人更可能是代理战争路线。",
    },
    "oil_price_100_breach": {
        "probability": 0.65,
        "confidence": 0.7,
        "reasoning": "预测节点。当前Brent $84，距$100还有19%。支撑因素：海峡封锁持续、沙特炼油关停。抑制因素：特朗普护航计划、亚洲LNG价格已回落(美方承诺保通)、IEA/日本可能释放战略储备。若封锁持续>2周则大概率突破。",
    },
    "trade_route_reshuffle": {
        "probability": 0.9,
        "confidence": 0.9,
        "reasoning": "半事实节点。中印转向俄油(确认)、Exxon从墨西哥湾运汽油到澳大利亚(确认)、中国暂停燃料出口(确认)。重组已在发生，但长期固化程度取决于冲突持续时间。",
    },
    "eu_nuclear_plan_b": {
        "label": "法德启动欧洲核保护伞扩展计划",
        "probability": 0.85,
        "confidence": 0.85,
        "reasoning": "半事实节点。法德已正式启动讨论(France and Germany launch Europe's nuclear Plan B, Readwise确认)。计划目标是将法国核保护伞扩展至其他欧洲NATO国家。但从'启动讨论'到'实际部署'仍有巨大差距，概率反映计划启动而非落地。",
    },
    "em_currency_crisis": {
        "probability": 0.7,
        "confidence": 0.65,
        "reasoning": "预测节点。驱动力确实存在(DXY走强+油价上涨双杀)，但'危机'一词意味着出现主权债务违约或资本管制等极端事件。目前印度VIX飙升62%后已回落15%。脆弱国家(土耳其/埃及/巴基斯坦)承压，但尚未触发系统性危机。0.93过高。",
    },
    "global_stagflation_risk": {
        "probability": 0.7,
        "confidence": 0.75,
        "reasoning": "预测节点。滞胀需要同时满足：通胀上升+增长放缓+失业上升。目前通胀预期确实在上行(美债定价)，但经济增长数据尚未全面恶化。若冲突在4-5周内结束(特朗普自己的时间表)，滞胀可能不会完全实现。0.93过高。",
    },
    "food_price_surge_global": {
        "probability": 0.55,
        "confidence": 0.6,
        "reasoning": "预测节点。传导链(天然气→化肥→粮价)逻辑成立，但存在时滞(2-3个月)。当前仅摩尔多瓦出现初步气荒迹象。粮价飙升需要持续的化肥短缺，而非短期冲击。0.68偏高。",
    },
    "oil_100_trigger_cascade": {
        "probability": 0.5,
        "confidence": 0.6,
        "reasoning": "预测节点。$100是CTA/量化基金止损密集区(锚定效应)，但程序化连锁需要突破速度快+成交量大。如果是缓慢爬升至$100，市场有时间消化，连锁效应会弱很多。",
    },
    "fed_policy_dilemma": {
        "probability": 0.6,
        "confidence": 0.6,
        "reasoning": "预测节点。美联储确实面临两难，但'困境'一词暗示被迫做出痛苦选择。如果冲突短期结束，油价回落，美联储可以继续按兵不动。只有在冲突长期化(>2个月)的情况下才会真正面临'沃尔克时刻'。",
    },
    "china_a_share_divergence": {
        "probability": 0.4,
        "confidence": 0.5,
        "reasoning": "预测节点。逻辑合理(中国非中东能源依赖+政策空间)，但A股历史上在全球风险事件中很少真正独立走强。更可能是'跌得少'而非'独立行情'。置信度低因为影响因素太多。",
    },
    "crypto_volatility_spike": {
        "label": "加密市场波动率上升",
        "probability": 0.85,
        "confidence": 0.85,
        "reasoning": "半事实节点。加密市场已证明在地缘危机中波动率确实上升(BTC跌破$66K后反弹$68.9K是3000美元级别的双向波动)。Euronews确认加密平台在传统市场闭市时成为主要交易场所。波动率上升是确定的，方向不确定。",
    },
    "defense_sector_boom": {
        "label": "军工订单确定性增长(长期)",
        "probability": 0.85,
        "confidence": 0.8,
        "reasoning": "预测节点。注意区分'股价'和'基本面'。短期股价因回购限制反跌(defense_stocks_paradox)，但长期订单增长几乎确定：$1.5万亿国防预算提案+弹药消耗需要补库。LMT/RTX高管已被召至白宫讨论加速生产。",
    },
    "energy_crisis_global": {
        "probability": 0.95,
        "confidence": 0.9,
        "reasoning": "半事实节点。能源危机的核心要素(海峡封锁、沙特炼油关停、卡塔尔LNG停产)均已发生。但'全球性危机'需要缺口持续>2周且无替代方案，目前日本/美国正在启动战略储备释放，中印转向俄油也在缓冲。0.98略高，因为存在局部缓解机制。",
    },
    "iran_regime_transition": {
        "probability": 0.85,
        "confidence": 0.7,
        "reasoning": "预测节点。哈梅内伊之死确实触发了继位程序，NYT/Reuters报道专家会议倾向莫杰塔巴。但(1)伊朗官方尚未正式确认(2)战时继位可能被推迟(3)存在IRGC直接军事接管的替代方案。1.0过高。",
    },
    "lng_spot_price_surge": {
        "probability": 0.95,
        "confidence": 0.9,
        "reasoning": "半事实节点。LNG运费已暴涨650%(确认)，但注意TTF期货在美方承诺保通海峡后已有回落(Asian LNG Prices Fall on U.S. Plan to Secure Hormuz Strait)。价格已在高位但不是单向上涨。",
    },
    "inflation_expectations_surge": {
        "probability": 0.7,
        "confidence": 0.7,
        "label": "通胀预期上行(盈亏平衡利率走阔)",
        "reasoning": "预测节点。10Y盈亏平衡利率走阔是事实，但'飙升至3.5%+'需要油价持续走高。若冲突在特朗普承诺的4-5周内结束，通胀预期可能在高位横盘而非继续飙升。",
    },
}

# ==========================================
# 执行修复
# ==========================================

# Step 1: 去重 - 删除重复节点，重定向边
edge_redirect = {
    "khamenei_assassinated": "khamenei_assassination",
    "iran_mass_retaliation_missiles": "iran_massive_retaliation",
    "mojtaba_khamenei_succession": "iran_regime_transition",
    "iran_1979_scale_protests": "iran_internal_protests",
    "global_energy_crisis_imminent": "energy_crisis_global",
    "gold_safe_haven_rally": "gold_record_high",
    "usd_strength_surge": "usd_dxy_surge",
    "global_equity_selloff": "sp500_selloff",
}

# Redirect edges
for e in edges:
    if e["source"] in edge_redirect:
        e["source"] = edge_redirect[e["source"]]
    if e["target"] in edge_redirect:
        e["target"] = edge_redirect[e["target"]]

# Remove duplicate edges after redirect
seen_edges = set()
deduped_edges = []
for e in edges:
    key = (e["source"], e["target"])
    if key not in seen_edges:
        seen_edges.add(key)
        deduped_edges.append(e)
edges = deduped_edges

# Remove duplicate nodes
for nid in DUPLICATES_TO_REMOVE:
    nodes.pop(nid, None)

# Step 2: Fix fact nodes
for nid, fixes in FACT_NODES_FIX.items():
    if nid in nodes:
        for k, v in fixes.items():
            nodes[nid][k] = v
        nodes[nid]["last_updated"] = datetime.now(timezone.utc).isoformat()

# Step 3: Fix prediction nodes
for nid, fixes in PREDICTION_FIXES.items():
    if nid in nodes:
        for k, v in fixes.items():
            nodes[nid][k] = v
        nodes[nid]["last_updated"] = datetime.now(timezone.utc).isoformat()

# Step 4: Clean up edges pointing to removed nodes
valid_nodes = set(nodes.keys())
edges = [e for e in edges if e["source"] in valid_nodes and e["target"] in valid_nodes]

# Step 5: Remove self-loops
edges = [e for e in edges if e["source"] != e["target"]]

# Save
dag["nodes"] = nodes
dag["edges"] = edges
dag["updated"] = datetime.now(timezone.utc).isoformat()

with open("data/dag.json", "w") as f:
    json.dump(dag, f, ensure_ascii=False, indent=2)

# Report
print(f"=== 审计完成 ===")
print(f"去重: 删除了 {len(DUPLICATES_TO_REMOVE)} 个重复节点")
print(f"修正: {len(FACT_NODES_FIX)} 个事实节点概率/reasoning")
print(f"修正: {len(PREDICTION_FIXES)} 个预测节点概率/reasoning")
print(f"剩余: {len(nodes)} 个节点, {len(edges)} 条边")

# Show final state
print(f"\n=== 修正后概率分布 ===")
fact_count = 0
pred_count = 0
for nid, n in sorted(nodes.items(), key=lambda x: -x[1]["probability"]):
    tag = "事实" if n["probability"] >= 0.95 else "预测"
    if tag == "事实": fact_count += 1
    else: pred_count += 1
    print(f"  [{tag}] {n['probability']:.2f} | {n['label']}")

print(f"\n事实节点: {fact_count}, 预测节点: {pred_count}")
