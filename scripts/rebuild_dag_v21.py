"""
DAG v21 Full Rebuild — US-Iran Conflict Scenario

Design principles:
1. 5-layer depth (event → state → 2nd-order → 3rd-order → 4th-order)
2. Both escalation AND de-escalation paths
3. China/Russia actor nodes (missing from v20)
4. Cross-domain transmission explicit at every hop
5. Probability calibration: events=100%, L1=80-95%, L2=60-85%, L3=40-70%, L4=20-50%
6. Every prediction reachable via ≥4 hops from a root
"""

import json
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat()

nodes = {}
edges = []

def N(id, label, nt, domains, prob, conf, reasoning, evidence=None, **kw):
    nodes[id] = {
        "id": id, "label": label, "node_type": nt,
        "domains": domains, "probability": prob, "confidence": conf,
        "evidence": evidence or [], "reasoning": reasoning,
        "time_horizon": kw.get("th", ""),
        "last_updated": now, "created": now,
    }

def E(src, tgt, w, reasoning=""):
    edges.append({"source": src, "target": tgt, "weight": w, "reasoning": reasoning})


# ═══════════════════════════════════════════════════════════════
# LAYER 0 — ROOT EVENTS (已发生, pinned)
# ═══════════════════════════════════════════════════════════════

N("us_israel_strikes", "美以联合空袭伊朗", "event", ["军事"],
  1.0, 0.99, "2026年2月底美以对伊朗核设施和军事基地发动大规模联合空袭",
  ["Reuters确认", "五角大楼声明"])

N("khamenei_killed", "哈梅内伊遇袭身亡", "event", ["军事", "政治"],
  1.0, 0.99, "最高领袖在空袭中遇难，触发伊朗政治真空",
  ["多方消息源确认", "IRGC声明"])

N("us_regime_change", "美国明确regime change意图", "event", ["政治"],
  1.0, 0.95, "白宫和国会多次表态支持伊朗政权更替",
  ["白宫声明", "众院219-212/参院47-52授权"])

N("iran_retaliation", "伊朗大规模报复(500导弹/2000无人机)", "event", ["军事"],
  1.0, 0.99, "IRGC发动史无前例的报复性打击，覆盖以色列和海湾美军基地",
  ["CENTCOM确认", "卫星图像"])

N("iran_gulf_attacks", "伊朗对全海湾国家发动攻击", "event", ["军事", "能源"],
  1.0, 0.99, "沙特/科威特/阿联酋/阿曼/巴林/阿塞拜疆均遭打击",
  ["多国防部声明", "巴林Ma'ameer炼油区遭无人机打击"])


# ═══════════════════════════════════════════════════════════════
# LAYER 1 — IMMEDIATE CONSEQUENCES (states, high certainty)
# ═══════════════════════════════════════════════════════════════

N("hormuz_blockade", "霍尔木兹海峡事实封锁", "state", ["军事", "能源"],
  0.88, 0.80, "伊朗水雷+反舰导弹+快艇使商船通行风险极高，保险费率飙升等效封锁。非完全物理封锁但商业通行实质中断。",
  th="持续至冲突结束")
E("iran_retaliation", "hormuz_blockade", 0.85, "报复行动包括海峡布雷和反舰导弹部署")
E("iran_gulf_attacks", "hormuz_blockade", 0.80, "全海湾攻击使所有油轮航线风险骤升")

N("iran_missile_degraded", "伊朗导弹能力被削弱90%(美方数据)", "state", ["军事"],
  0.85, 0.70, "美方称打击使伊朗中远程导弹库存消耗殆尽。但伊朗保有分散的短程系统和无人机生产线。85%反映美方数据可能夸大。",
  th="持续")
E("us_israel_strikes", "iran_missile_degraded", 0.90, "空袭主要目标之一就是导弹基地")
E("iran_retaliation", "iran_missile_degraded", 0.70, "大规模发射本身消耗了大量库存")

N("regional_spillover", "冲突外溢至海湾6国", "state", ["军事", "政治"],
  0.92, 0.85, "伊朗全海湾攻击使冲突从双边升级为区域性战争",
  th="持续")
E("iran_gulf_attacks", "regional_spillover", 0.95, "全海湾攻击直接导致外溢")

N("shipping_insurance_collapse", "航运保险市场崩溃", "state", ["金融", "能源"],
  0.95, 0.90, "波斯湾战争险费率飙升至货物价值15-20%，大量船东拒绝挂靠海湾港口",
  th="持续至冲突结束")
E("hormuz_blockade", "shipping_insurance_collapse", 0.95, "海峡封锁直接导致保险市场崩溃")
E("iran_gulf_attacks", "shipping_insurance_collapse", 0.80, "炼油设施遭袭使港口风险激增")

N("iran_power_transition", "伊朗权力交接(莫杰塔巴继位)", "state", ["政治"],
  0.82, 0.65, "IRGC内部协调推动莫杰塔巴·哈梅内伊为继任者，但政治真空期IRGC各派系权力博弈加剧。82%反映继位大概率但非确定。",
  th="3-6个月过渡期")
E("khamenei_killed", "iran_power_transition", 0.90, "最高领袖死亡触发继位程序")

N("pentagon_war_cost", "五角大楼战争开支已超$50亿", "event", ["政治", "经济"],
  1.0, 0.95, "确认的财政支出数据", ["国会预算办公室报告"])
E("us_israel_strikes", "pentagon_war_cost", 0.90, "空袭行动的直接军费")


# ═══════════════════════════════════════════════════════════════
# LAYER 2 — ENERGY & MILITARY TRANSMISSION
# ═══════════════════════════════════════════════════════════════

N("energy_crisis", "全球能源危机爆发", "state", ["能源", "经济"],
  0.92, 0.85, "霍尔木兹封锁切断全球~20%石油和25%LNG贸易量，叠加海湾炼厂受损",
  th="持续至航线恢复")
E("hormuz_blockade", "energy_crisis", 0.90, "海峡封锁直接切断能源供应")
E("shipping_insurance_collapse", "energy_crisis", 0.75, "保险崩溃使替代航线成本也飙升")

N("oil_price_100", "Brent突破$100/桶", "prediction", ["能源", "金融"],
  0.88, 0.75, "当前Brent~$85，供应中断+恐慌溢价可推至$100+。但SPR释放和需求萎缩构成上方阻力。",
  th="W1-4")
E("energy_crisis", "oil_price_100", 0.85, "供应危机直接推高油价")
E("hormuz_blockade", "oil_price_100", 0.80, "封锁预期已部分price in")

N("asia_refinery_cuts", "亚洲炼厂因原油供应中断削减产能", "state", ["能源", "经济"],
  0.85, 0.75, "中日韩印炼厂高度依赖中东原油，替代来源需6-8周调整",
  th="W2-8")
E("energy_crisis", "asia_refinery_cuts", 0.85, "原油断供直接影响亚洲炼厂")
E("hormuz_blockade", "asia_refinery_cuts", 0.80, "海峡封锁切断主要供应线")

N("qatar_lng_disrupted", "卡塔尔LNG出口受阻", "state", ["能源"],
  0.80, 0.70, "卡塔尔LNG经霍尔木兹出口，封锁使其被迫减产或绕行。卡塔尔本身试图保持中立但地理位置使其无法避免影响。",
  th="持续至航线恢复")
E("hormuz_blockade", "qatar_lng_disrupted", 0.85, "LNG运输必经海峡")
E("regional_spillover", "qatar_lng_disrupted", 0.60, "区域冲突波及卡塔尔设施安全")

N("coalition_forming", "多国反伊朗军事联盟形成", "state", ["军事", "政治"],
  0.75, 0.65, "美国牵头组建联军，英法已部署。但联盟内部分歧大——欧洲不愿全面参战。",
  th="W1-4")
E("us_regime_change", "coalition_forming", 0.70, "regime change需要联盟支撑")
E("regional_spillover", "coalition_forming", 0.75, "海湾国家遭袭后寻求集体防御")

N("secondary_sanctions", "美国发起二级制裁潮", "state", ["政治", "经济"],
  0.82, 0.80, "切断伊朗残余贸易网络，波及中国/印度/土耳其企业",
  th="W2-8")
E("us_regime_change", "secondary_sanctions", 0.85, "regime change战略需要经济绞杀配合")

N("irgc_nuclear", "IRGC加速核武计划(突破90%浓缩铀)", "prediction", ["军事", "政治"],
  0.55, 0.50, "IRGC在生存威胁下可能加速核突破。但关键设施已遭打击，技术路径受损。55%反映意愿高但能力受限。",
  th="W8-24")
E("us_israel_strikes", "irgc_nuclear", 0.60, "打击反而激发核武器动机")
E("iran_power_transition", "irgc_nuclear", 0.55, "权力真空中IRGC可能自主决策")
E("iran_missile_degraded", "irgc_nuclear", 0.50, "常规威慑丧失增加核补偿动机")

N("kurdish_proxy", "CIA武装库尔德人开辟地面战线", "state", ["军事", "政治"],
  0.68, 0.60, "历史先例+当前局势使代理人战争可能性高。但土耳其反对构成制约。",
  th="W4-16")
E("us_regime_change", "kurdish_proxy", 0.75, "regime change需要地面力量配合")

# === NEW: 大国角色 ===

N("china_energy_diplomacy", "中国能源外交斡旋", "state", ["政治", "能源"],
  0.70, 0.60, "中国是伊朗最大石油买家，有动机推动停火以保供应链。但中美关系限制斡旋空间。",
  th="W2-12")
E("energy_crisis", "china_energy_diplomacy", 0.65, "能源危机直接威胁中国经济")
E("secondary_sanctions", "china_energy_diplomacy", 0.55, "二级制裁威胁中国企业")

N("russia_energy_leverage", "俄罗斯借能源危机增加地缘杠杆", "state", ["政治", "能源"],
  0.78, 0.70, "俄罗斯作为替代能源供应方获益，同时在联合国为伊朗提供外交掩护。能源价格上涨缓解其制裁压力。",
  th="持续")
E("energy_crisis", "russia_energy_leverage", 0.80, "能源危机直接增强俄方谈判筹码")

N("ceasefire_backchannel", "停火后渠道谈判", "prediction", ["政治"],
  0.35, 0.40, "当前无明确谈判信号。美方'permanent features'表态+国会两党支持使退出成本极高。35%反映仍有微弱外交窗口。",
  th="W4-16")
E("china_energy_diplomacy", "ceasefire_backchannel", 0.50, "中国可能提供调解渠道")
E("iran_power_transition", "ceasefire_backchannel", 0.40, "新领导层可能有不同战略取向")


# ═══════════════════════════════════════════════════════════════
# LAYER 3 — SECOND-ORDER EFFECTS
# ═══════════════════════════════════════════════════════════════

N("conflict_protracted", "冲突持续超过2个月", "prediction", ["军事", "政治"],
  0.80, 0.70, "双方均无退出机制：美方受众成本锁定，伊朗IRGC不可能接受regime change。承诺悖论：杀了谈判对手谁签停火。",
  th="W8+")
E("us_regime_change", "conflict_protracted", 0.80, "regime change目标使速战速决不可能")
E("iran_power_transition", "conflict_protracted", 0.65, "权力真空期无人有权签署停火")
E("coalition_forming", "conflict_protracted", 0.55, "联盟结构增加退出协调成本")

N("us_ground_war", "美军地面部队入伊朗", "prediction", ["军事", "政治"],
  0.45, 0.50, "国会已授权但国内反战情绪+伊拉克/阿富汗教训构成制约。空中力量为主、地面有限介入更可能。",
  th="W8-24")
E("conflict_protracted", "us_ground_war", 0.60, "持久冲突增加地面介入压力")
E("us_regime_change", "us_ground_war", 0.55, "regime change最终需要地面力量")
E("iran_missile_degraded", "us_ground_war", 0.40, "导弹威慑降低使地面行动风险下降")

N("europe_energy_crisis", "欧洲爆发第二次能源危机(TTF>€80)", "prediction", ["能源", "经济"],
  0.72, 0.65, "卡塔尔LNG中断+天然气现货价飙升。欧洲已从俄气转向LNG，但LNG供应链脆弱。",
  th="W2-12")
E("qatar_lng_disrupted", "europe_energy_crisis", 0.80, "LNG中断直接冲击欧洲")
E("energy_crisis", "europe_energy_crisis", 0.70, "全球能源危机传导至欧洲")

N("global_stagflation", "全球经济进入滞胀(通胀>4%+GDP<1%)", "prediction", ["经济"],
  0.68, 0.60, "油价冲击推高通胀+需求萎缩压制增长。但各国财政空间和货币政策响应可能缓冲。历史类比1973但全球化程度不同。",
  th="W8-24")
E("energy_crisis", "global_stagflation", 0.75, "能源危机是滞胀的经典触发器")
E("oil_price_100", "global_stagflation", 0.70, "油价突破$100加速通胀预期")

N("fed_dilemma", "美联储两难(通胀vs增长)", "prediction", ["金融", "经济"],
  0.85, 0.75, "供给侧通胀+需求萎缩的教科书困境。当前市场预期分裂。",
  th="W4-16")
E("global_stagflation", "fed_dilemma", 0.85, "滞胀直接制造政策两难")
E("oil_price_100", "fed_dilemma", 0.65, "油价推高通胀预期")

N("em_debt_crisis", "新兴市场出现主权债务危机", "prediction", ["金融", "经济"],
  0.62, 0.55, "美元走强+能源成本飙升+资本外流三重冲击。但IMF缓冲+各国外储改善提供韧性。62%而非90%+。",
  th="W8-24")
E("global_stagflation", "em_debt_crisis", 0.65, "滞胀环境恶化EM基本面")
E("energy_crisis", "em_debt_crisis", 0.60, "能源进口国经常账恶化")

N("equity_correction", "全球股市回调(S&P -5%+)", "prediction", ["金融"],
  0.78, 0.70, "风险偏好急剧下降+盈利预期下调。但央行可能提供流动性支持。",
  th="W1-4")
E("energy_crisis", "equity_correction", 0.70, "能源冲击打击企业盈利")
E("global_stagflation", "equity_correction", 0.65, "滞胀预期压制估值")

N("safe_haven_rally", "避险资产(黄金/美元)持续跑赢", "state", ["金融"],
  0.82, 0.75, "经典risk-off交易。黄金已创新高$5183。避险需求强劲。",
  th="持续")
E("energy_crisis", "safe_haven_rally", 0.75, "危机推动避险需求")
E("equity_correction", "safe_haven_rally", 0.70, "股市回调加速避险")

N("treasury_stagflation", "美债定价滞胀(10Y>4%)", "state", ["金融"],
  0.75, 0.65, "通胀预期上行压制避险买盘。10Y yield在通胀和避险之间拉锯。",
  th="W2-12")
E("global_stagflation", "treasury_stagflation", 0.80, "滞胀直接推高长端利率")
E("fed_dilemma", "treasury_stagflation", 0.65, "政策不确定性增加期限溢价")

N("food_price_surge", "全球粮食价格飙升(化肥传导链)", "prediction", ["经济", "社会"],
  0.65, 0.55, "天然气是化肥原料→化肥涨价→粮食涨价。传导链长(3-6个月)，期间有替代可能。",
  th="W8-24")
E("energy_crisis", "food_price_surge", 0.65, "能源→化肥→粮食传导链")
E("europe_energy_crisis", "food_price_surge", 0.50, "欧洲化肥产能受限")

N("trade_route_reshuffle", "全球能源贸易路线重组", "prediction", ["能源", "经济"],
  0.78, 0.70, "好望角绕行+亚洲转向大西洋盆地+LNG现货市场重构",
  th="W4-24")
E("hormuz_blockade", "trade_route_reshuffle", 0.85, "海峡封锁迫使航线调整")
E("shipping_insurance_collapse", "trade_route_reshuffle", 0.70, "保险成本差异驱动路线选择")


# ═══════════════════════════════════════════════════════════════
# LAYER 4 — THIRD-ORDER / CROSS-DOMAIN
# ═══════════════════════════════════════════════════════════════

N("iran_internal_crisis", "伊朗爆发大规模反政府抗议", "prediction", ["政治", "社会"],
  0.55, 0.50, "领导真空+经济制裁+军事失败可能触发。但IRGC镇压能力仍在。",
  th="W8-24")
E("iran_power_transition", "iran_internal_crisis", 0.60, "权力真空削弱社会控制")
E("secondary_sanctions", "iran_internal_crisis", 0.50, "经济恶化加剧民怨")

N("eu_defense_surge", "欧洲防务开支加速(GDP 2%+)", "prediction", ["政治", "经济"],
  0.72, 0.65, "海湾冲突暴露欧洲防务依赖美国的脆弱性",
  th="W8-24+")
E("regional_spillover", "eu_defense_surge", 0.65, "区域战争刺激欧洲安全意识")
E("europe_energy_crisis", "eu_defense_surge", 0.55, "能源脆弱性→战略自主需求")

N("refugee_wave", "中东难民潮涌入欧洲(≥50万)", "prediction", ["社会", "政治"],
  0.55, 0.50, "冲突持续+经济崩溃推动人口流动。路线经土耳其/地中海。",
  th="W12-24+")
E("conflict_protracted", "refugee_wave", 0.65, "持久冲突是难民潮主因")
E("iran_internal_crisis", "refugee_wave", 0.50, "伊朗国内危机加速外流")

N("us_domestic_pressure", "美国国内政治反弹(汽油>$5)", "prediction", ["政治"],
  0.58, 0.55, "油价传导至零售端需4-6周。汽油价是美国选民最敏感的经济指标。",
  th="W4-12")
E("oil_price_100", "us_domestic_pressure", 0.70, "油价→汽油价→政治压力")
E("pentagon_war_cost", "us_domestic_pressure", 0.50, "战争开支引发财政质疑")

N("credit_tightening", "高收益债利差走阔>500bp", "prediction", ["金融"],
  0.58, 0.50, "能源冲击+滞胀→企业信用恶化。但量化宽松的记忆使市场期待央行干预。",
  th="W4-16")
E("global_stagflation", "credit_tightening", 0.65, "滞胀恶化企业基本面")
E("equity_correction", "credit_tightening", 0.55, "股市下跌与信贷紧缩正反馈")

N("cny_depreciation", "人民币有序贬值突破7.0", "prediction", ["金融", "外汇"],
  0.62, 0.55, "能源进口成本飙升+外需萎缩。PBOC有管理贬值的工具和意愿。",
  th="W4-16")
E("energy_crisis", "cny_depreciation", 0.60, "能源进口恶化经常账")
E("em_debt_crisis", "cny_depreciation", 0.50, "EM风险传染")

N("jpy_carry_unwind", "日元套利交易大规模平仓(USD/JPY<150)", "prediction", ["金融", "外汇"],
  0.48, 0.45, "risk-off环境下carry unwind可能性。但BoJ利率仍低，carry仍有吸引力。",
  th="W2-8")
E("safe_haven_rally", "jpy_carry_unwind", 0.55, "避险情绪触发carry unwind")
E("equity_correction", "jpy_carry_unwind", 0.50, "股市回调迫使杠杆平仓")

N("euro_parity", "欧元跌破对美元平价", "prediction", ["金融", "外汇"],
  0.52, 0.45, "欧洲能源危机+ECB两难+美元避险需求。但欧元区经常账改善提供支撑。",
  th="W4-16")
E("europe_energy_crisis", "euro_parity", 0.65, "能源危机打击欧元基本面")
E("safe_haven_rally", "euro_parity", 0.50, "美元避险需求压制欧元")


# ═══════════════════════════════════════════════════════════════
# LAYER 5 — FOURTH-ORDER / TAIL & DE-ESCALATION
# ═══════════════════════════════════════════════════════════════

N("conflict_deescalation", "冲突降级/部分停火", "prediction", ["政治", "军事"],
  0.25, 0.35, "当前极低。美方承诺不可逆(选举年+两党联名)，伊朗IRGC无法接受regime change。需要外部冲击(如重大军事挫折)才能改变。",
  th="W12-24+")
E("ceasefire_backchannel", "conflict_deescalation", 0.50, "后渠道谈判是降级前提")
E("us_domestic_pressure", "conflict_deescalation", 0.45, "国内反弹可能迫使降级")
E("china_energy_diplomacy", "conflict_deescalation", 0.35, "中国斡旋提供外交台阶")

N("turkey_intervention", "土耳其因库尔德问题介入风险", "prediction", ["军事", "政治"],
  0.35, 0.40, "CIA武装库尔德人直接触及土耳其红线。但北约身份限制其公开反美。",
  th="W8-24")
E("kurdish_proxy", "turkey_intervention", 0.65, "库尔德武装是土耳其核心关切")
E("regional_spillover", "turkey_intervention", 0.40, "区域冲突扩大土耳其风险暴露")

N("em_food_riots", "新兴市场爆发食品价格骚乱(≥3国)", "prediction", ["社会"],
  0.40, 0.40, "粮价飙升→社会动荡。历史先例：2008/2011阿拉伯之春前夜。",
  th="W12-24+")
E("food_price_surge", "em_food_riots", 0.60, "粮价是社会稳定的直接触发器")
E("em_debt_crisis", "em_food_riots", 0.45, "经济危机放大社会脆弱性")

N("ecb_rate_reversal", "ECB从降息转向加息", "prediction", ["金融", "经济"],
  0.38, 0.40, "能源通胀可能迫使ECB转向。但增长放缓构成强制约。低于50%。",
  th="W8-24")
E("europe_energy_crisis", "ecb_rate_reversal", 0.60, "能源通胀倒逼加息")
E("global_stagflation", "ecb_rate_reversal", 0.50, "滞胀压力传导")

N("wartime_capital_controls", "战时经济政策(回购限制/产能管制)", "prediction", ["政治", "经济"],
  0.30, 0.35, "需要国会行动+极端经济环境。当前还远未到这个程度。",
  th="W16-24+")
E("conflict_protracted", "wartime_capital_controls", 0.50, "持久冲突增加战时动员需求")
E("us_domestic_pressure", "wartime_capital_controls", 0.40, "政治压力可能触发经济干预")

N("oil_new_equilibrium", "原油市场找到新均衡($85-100区间)", "prediction", ["能源", "金融"],
  0.55, 0.45, "SPR释放+替代供应+需求萎缩最终压制油价。但均衡在什么水平取决于冲突持续时间。",
  th="W8-16")
E("oil_price_100", "oil_new_equilibrium", 0.60, "超调后市场寻找均衡")
E("trade_route_reshuffle", "oil_new_equilibrium", 0.55, "新贸易路线重新定价供应链")
E("conflict_deescalation", "oil_new_equilibrium", 0.45, "停火信号会加速价格回落")

N("europe_right_wing", "欧洲右翼政党显著上升(+5%)", "prediction", ["政治", "社会"],
  0.50, 0.45, "难民潮+能源危机+经济衰退的政治后果。历史模式清晰。",
  th="W12-24+")
E("refugee_wave", "europe_right_wing", 0.65, "难民问题是右翼崛起的核心议题")
E("europe_energy_crisis", "europe_right_wing", 0.50, "能源危机加剧反建制情绪")

N("eu_nuclear_umbrella", "法德启动欧洲核保护伞计划", "prediction", ["军事", "政治"],
  0.40, 0.35, "长期战略议题，当前冲突加速讨论但落地需要数年。",
  th="W16+")
E("eu_defense_surge", "eu_nuclear_umbrella", 0.55, "防务加速是核伞计划的前提")
E("irgc_nuclear", "eu_nuclear_umbrella", 0.50, "伊朗核突破刺激欧洲核自主需求")

N("crypto_risk_correlation", "加密资产与风险资产保持高相关性", "state", ["金融"],
  0.65, 0.55, "BTC已跌破$66K。在宏观risk-off环境中加密不是避险资产。",
  th="持续")
E("equity_correction", "crypto_risk_correlation", 0.65, "股市回调带动加密下跌")
E("jpy_carry_unwind", "crypto_risk_correlation", 0.45, "杠杆平仓波及加密")


# ═══════════════════════════════════════════════════════════════
# CROSS-DOMAIN BRIDGES (补充关键跨域传导)
# ═══════════════════════════════════════════════════════════════

# 政治→金融
E("us_domestic_pressure", "equity_correction", 0.35, "政治不确定性压制市场信心")

# 金融→政治反馈
E("em_debt_crisis", "us_domestic_pressure", 0.30, "全球经济恶化加剧国内批评")

# 军事→能源补充
E("coalition_forming", "hormuz_blockade", 0.30, "联军巡逻可能部分缓解封锁(负相关)")
# Note: this edge is actually dampening — coalition helps open strait. Weight low.

# 中国→金融
E("china_energy_diplomacy", "cny_depreciation", -0.30, "成功斡旋可能缓解人民币压力")

# 俄罗斯→能源
E("russia_energy_leverage", "oil_new_equilibrium", 0.40, "俄罗斯增产填补缺口但有地缘政治条件")


# ═══════════════════════════════════════════════════════════════
# BUILD & SAVE
# ═══════════════════════════════════════════════════════════════

dag = {
    "scenario": "us_iran_conflict",
    "scenario_label": "美伊冲突升级",
    "version": 21,
    "updated": now,
    "nodes": nodes,
    "edges": edges,
}

# Validate
sources = {e["source"] for e in edges}
targets = {e["target"] for e in edges}
all_edge_nodes = sources | targets
orphans = [nid for nid in nodes if nid not in all_edge_nodes]
missing = (all_edge_nodes) - set(nodes.keys())
root_nodes = [nid for nid in nodes if nid not in targets]
leaf_nodes = [nid for nid in nodes if nid not in sources]

print(f"DAG v21 Built:")
print(f"  Nodes: {len(nodes)}")
print(f"  Edges: {len(edges)}")
print(f"  Roots: {len(root_nodes)} → {root_nodes}")
print(f"  Leaves: {len(leaf_nodes)}/{len(nodes)} = {len(leaf_nodes)/len(nodes)*100:.0f}%")
print(f"  Orphans: {orphans}")
print(f"  Missing refs: {missing}")

# Type distribution
types = {}
for n in nodes.values():
    t = n["node_type"]
    types[t] = types.get(t, 0) + 1
print(f"  Types: {types}")

# Domain distribution
domains = {}
for n in nodes.values():
    for d in n["domains"]:
        domains[d] = domains.get(d, 0) + 1
print(f"  Domains: {dict(sorted(domains.items(), key=lambda x:-x[1]))}")

# Check max depth
def bfs_depth(roots, edges_list):
    adj = {}
    for e in edges_list:
        adj.setdefault(e["source"], []).append(e["target"])
    max_d = 0
    for r in roots:
        q = [(r, 0)]
        visited = set()
        while q:
            n, d = q.pop(0)
            if n in visited: continue
            visited.add(n)
            max_d = max(max_d, d)
            for c in adj.get(n, []):
                q.append((c, d+1))
    return max_d

md = bfs_depth(root_nodes, edges)
print(f"  Max depth: {md}")

if not missing and not orphans:
    with open("data/dag.json", "w") as f:
        json.dump(dag, f, indent=2, ensure_ascii=False)
    print("\n✅ Saved to data/dag.json")
else:
    print(f"\n❌ Validation failed: orphans={orphans}, missing={missing}")
