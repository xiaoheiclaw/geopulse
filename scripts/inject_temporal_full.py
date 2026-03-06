"""Inject temporal probability + dialectic for all remaining key nodes."""
import json
from datetime import datetime, timezone

dag = json.load(open("data/dag.json"))
nodes = dag["nodes"]

# ================================================================
# BATCH: Time phases + Dialectics for all remaining nodes
# ================================================================

updates = {
    # ===================== HIGH PRIORITY: State nodes =====================
    
    "energy_crisis_global": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "急性冲击", "prob_density": 0.0,
             "triggers": ["三大中断同步"], "signals": ["Brent日波动"], "actions": ["已发生,持仓不动"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "护航测试", "prob_density": 0.0,
             "triggers": ["美方护航效果"], "signals": ["首批商船通过?","亚洲LNG价格"], "actions": ["护航成功→能源空头"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "库存临界 ★", "prob_density": 0.0,
             "triggers": ["SPR耗尽(韩国9天/欧洲6-8周)"], "signals": ["IEA月度库存报告"], "actions": ["库存跌破警戒→加码能源多头"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "慢性化", "prob_density": 0.0,
             "triggers": ["替代路线固化(中印→俄油)"], "signals": ["Brent远月曲线结构"], "actions": ["慢性化→转看通胀链"]},
        ],
        "dialectic": {
            "thesis": "持续(80%): 三大中断同步(海峡+沙特+卡塔尔)是史无前例的。页岩无法替代(物理约束)。亚洲炼厂已减产。",
            "antithesis": "缓解(20%): 战略储备释放+替代路线(俄油)正在缓冲。卡塔尔停产不会引发长期螺旋(分析师共识)。浮式LNG终端是2022后新增能力。",
            "synthesis": "危机从'急性'转为'慢性'。最坏时刻可能已过(恐慌定价→均衡定价),但结构性缺口至少持续到护航恢复海峡通行。",
            "revision_history": ["v1 0.95→v2 0.80→v3 0.75: 护航计划+储备释放→逐步下调"]
        }
    },

    "hormuz_blockade_de_facto": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "完全封锁", "prob_density": 0.0,
             "triggers": ["保险撤离+USV+恐惧"], "signals": ["AIS船舶数据"], "actions": ["持仓不动"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "护航测试 ★", "prob_density": 0.0,
             "triggers": ["首批护航船队出发"], "signals": ["第一艘非中/伊商船安全通过"], "actions": ["通过→封锁概率大降→做空油价"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "分叉", "prob_density": 0.0,
             "triggers": ["护航成功→逐步恢复 vs 水雷/USV阻止"], "signals": ["保险公司试探性恢复承保"], "actions": ["跟踪保险市场"]},
        ]
    },

    "safe_haven_outperformance": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "恐慌避险", "prob_density": 0.0,
             "triggers": ["初始冲击"], "signals": ["黄金日波动"], "actions": ["持有黄金"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "避险持续", "prob_density": 0.0,
             "triggers": ["冲突未降级"], "signals": ["DXY趋势"], "actions": ["加仓金矿"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "逻辑切换 ★", "prob_density": 0.0,
             "triggers": ["从避险→通胀对冲"], "signals": ["实际利率趋势"], "actions": ["黄金从避险逻辑切到通胀逻辑→更持久"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "通胀对冲", "prob_density": 0.0,
             "triggers": ["通胀锚定上移"], "signals": ["央行购金数据"], "actions": ["黄金核心多头"]},
        ]
    },

    "treasury_stagflation_pricing": {
        "dialectic": {
            "thesis": "持续(75%): 通胀预期上行压制避险买盘。DB说'无避险需求迹象'。10Y 4.09%且在上行。军费赤字扩张推高长端。",
            "antithesis": "回落(25%): 若冲突短期结束,通胀预期回落→10Y可能跌破4%。美债仍是全球最深流动性池,极端恐慌时仍会买入。",
            "synthesis": "滞胀定价是当前主导逻辑,但有上限——如果恐慌升级到'全面战争'级别,避险逻辑可能短暂压过通胀逻辑(参考2020.03)。",
            "revision_history": ["从'避险失灵'重新定义为'滞胀定价'(DT纠错)"]
        }
    },

    # ===================== PREDICTION NODES =====================

    "equity_correction_deepening": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "初始卖出", "prob_density": 0.05,
             "triggers": ["恐慌抛售"], "signals": ["VIX>25"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "消化", "prob_density": 0.10,
             "triggers": ["市场试探底部"], "signals": ["S&P技术支撑位"], "actions": ["等待"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "盈利下修 ★", "prob_density": 0.20,
             "triggers": ["Q1盈利预告→下修","油价成本传导"], "signals": ["SPX EPS修正比率"], "actions": ["做空高估值成长"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "通胀杀估值", "prob_density": 0.15,
             "triggers": ["Fed困境明确→利率预期上修"], "signals": ["PE压缩幅度"], "actions": ["加码空头"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "底部", "prob_density": 0.10,
             "triggers": ["估值洗完→选择性抄底"], "signals": ["VIX回落<20"], "actions": ["选择性多头:能源/防务"]},
        ],
        "dialectic": {
            "thesis": "深跌(60%): 历史ME战争avg -8~-12%回调。当前仅-2.5%,空间很大。通胀传导→盈利下修→PE压缩三重打击。",
            "antithesis": "浅跌(40%): S&P在6710-7002窄幅震荡(Newton:最窄区间),说明市场有支撑。美国经济基本面仍健康。能源自给限制了对美股的直接冲击。",
            "synthesis": "回调幅度取决于冲突持续时间。<1月→-5%然后反弹; 2-4月→-8~-12%; >4月→-15%+(叠加信贷紧缩)。",
            "revision_history": ["v1 0.55→v2 0.60: 全海湾攻击扩大尾部风险"]
        }
    },

    "fed_policy_dilemma": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "观望", "prob_density": 0.0,
             "triggers": ["太早"], "signals": [], "actions": ["Fed不会反应"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "措辞调整", "prob_density": 0.02,
             "triggers": ["FOMC声明加入地缘风险措辞"], "signals": ["Fed官员讲话"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "数据拐点", "prob_density": 0.08,
             "triggers": ["CPI开始反映油价","就业初步放缓"], "signals": ["核心CPI环比>0.4%"], "actions": ["建仓TIPS"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "困境显化 ★", "prob_density": 0.15,
             "triggers": ["通胀+增长同时恶化"], "signals": ["FOMC点阵图分裂"], "actions": ["做多曲线陡峭化"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "被迫表态", "prob_density": 0.10,
             "triggers": ["不加不行(通胀)或不降不行(增长)"], "signals": ["紧急会议?"], "actions": ["跟随Fed方向"]},
        ]
    },

    "food_price_surge_global": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "无影响", "prob_density": 0.0,
             "triggers": [], "signals": [], "actions": ["太早"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "化肥涨价", "prob_density": 0.02,
             "triggers": ["天然气→化肥成本+30%"], "signals": ["尿素期货"], "actions": ["观察化肥股"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "种植季冲击 ★", "prob_density": 0.10,
             "triggers": ["北半球春播季→化肥需求峰值","补贴国预算压力"], "signals": ["CBOT小麦/玉米"], "actions": ["做多农业(K+F/Mosaic)"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "粮价传导", "prob_density": 0.15,
             "triggers": ["化肥→粮价传导完成","EM补贴耗尽"], "signals": ["FAO食品价格指数"], "actions": ["做空EM食品进口国货币"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "社会效应", "prob_density": 0.10,
             "triggers": ["粮价→社会动荡(2011先例)"], "signals": ["EM抗议新闻"], "actions": ["tail hedge EM政治风险"]},
        ]
    },

    "iran_regime_transition": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "权力真空", "prob_density": 0.05,
             "triggers": ["哈梅内伊死亡→紧急继位"], "signals": ["伊朗国家电视台"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "IRGC主导 ★", "prob_density": 0.20,
             "triggers": ["Assembly of Experts投票","IRGC施压"], "signals": ["Mojtaba公开露面"], "actions": ["关注核政策信号"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "巩固期", "prob_density": 0.20,
             "triggers": ["新领袖首次重大政策声明"], "signals": ["对外沟通渠道是否开启"], "actions": ["影响停火概率判断"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "稳定/分裂", "prob_density": 0.15,
             "triggers": ["内部权力斗争?"], "signals": ["IRGC vs 文官政府关系"], "actions": ["分裂→冲突长期化"]},
        ],
        "dialectic": {
            "thesis": "快速继位(65%): Mojtaba是最大概率方案。IRGC需要统一指挥链。Assembly of Experts已投票(虽被质疑)。",
            "antithesis": "延迟/军事委员会(35%): 战时条件下正式继位可能推迟。IRGC可能维持'临时领导委员会'以保持灵活性。Trump公开要选下任领导人→反而强化内部团结延迟正式交接。",
            "synthesis": "Mojtaba名义继位概率高，但实际权力巩固需要2-4个月。关键问题不是谁继位，而是新领导人能否做出可信的停火承诺(承诺悖论)。",
            "revision_history": ["v1 0.85→v2 0.70→v3 0.65: 考虑战时延迟+IRGC过渡可能"]
        }
    },

    "iran_internal_protests": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "rally around flag", "prob_density": 0.02,
             "triggers": ["外部威胁→内部团结"], "signals": ["伊朗社交媒体(VPN)"], "actions": ["不行动"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "哀悼→愤怒?", "prob_density": 0.05,
             "triggers": ["哈梅内伊葬礼后→情绪转变?"], "signals": ["互联网封锁是否放松"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "经济压力", "prob_density": 0.10,
             "triggers": ["战争经济崩溃","日用品短缺"], "signals": ["里亚尔汇率"], "actions": ["影响regime transition判断"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "镇压疲劳", "prob_density": 0.15,
             "triggers": ["IRGC镇压资源分散(前线+内部)"], "signals": ["地方城市抗议报道"], "actions": ["大规模抗议→regime change加速"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "2019重演?", "prob_density": 0.13,
             "triggers": ["长期战争→经济全面崩溃→2019/2022抗议重演"], "signals": ["联合国人权报告"], "actions": [""]},
        ],
        "dialectic": {
            "thesis": "抗议爆发(45%): 经济已在崩溃(里亚尔暴跌)。IRGC资源分散在前线和内部。2022/2025抗议显示社会基础存在。",
            "antithesis": "压制成功(55%): 外部威胁触发rally-around-flag。互联网封锁限制组织能力。IRGC镇压效率极高(2022经验)。战时'叛国'叙事压制异见。",
            "synthesis": "短期(<1月)抗议概率低(rally-around-flag)。中期(2-4月)随战争经济崩溃→概率跃升。关键变量是IRGC能否同时维持前线和内部控制。",
            "revision_history": ["v1 0.85→v2 0.50→v3 0.45: 大幅下调,rally-around-flag效应被低估"]
        }
    },

    "europe_energy_crisis_redux": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "LNG价格跳涨", "prob_density": 0.03,
             "triggers": ["卡塔尔LNG停产"], "signals": ["TTF日K"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "库存消耗", "prob_density": 0.07,
             "triggers": ["补库季开始但无货源"], "signals": ["EU库存周报"], "actions": ["做多EU天然气"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "补库季危机 ★", "prob_density": 0.15,
             "triggers": ["4-5月正常补库→今年补不上→冬季恐慌前置"], "signals": ["TTF>€80"], "actions": ["做多TTF远月"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "政策应对", "prob_density": 0.15,
             "triggers": ["需求毁灭+紧急采购"], "signals": ["EU紧急能源峰会"], "actions": ["跟踪ECB反应"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "冬季定价", "prob_density": 0.15,
             "triggers": ["市场开始为2026/27冬季定价"], "signals": ["远月曲线"], "actions": ["长期多头"]},
        ],
        "dialectic": {
            "thesis": "危机重演(55%): 卡塔尔=欧洲LNG 15%。补库季即将开始。TTF可能冲€100(Reuters)。需求毁灭是唯一平衡机制。",
            "antithesis": "可控(45%): 规模比2022小(卡塔尔15% vs 俄罗斯40%)。欧洲有2022后建的浮式LNG终端。美国LNG出口可部分补缺。",
            "synthesis": "比2022小但不可忽视。关键窗口是补库季(4-10月)——如果卡塔尔停产>4周+补库空转→冬季前恐慌。€80是警戒线。",
            "revision_history": ["v1 0.50→v2 0.55: UK基地遭击+5国部署→欧洲被卷入"]
        }
    },

    "ecb_rate_reversal": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "暂停降息", "prob_density": 0.0,
             "triggers": ["MS+BofA撤回降息预期"], "signals": ["ECB官员讲话"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "数据等待", "prob_density": 0.02,
             "triggers": ["等能源价格传导至HICP"], "signals": ["EU flash CPI"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "通胀抬头", "prob_density": 0.05,
             "triggers": ["核心HICP上行"], "signals": ["ECB工作人员预测修正"], "actions": ["做空德国国债"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "立场转变 ★", "prob_density": 0.10,
             "triggers": ["二阶通胀效应(工资)出现"], "signals": ["ECB前瞻指引变化"], "actions": ["做空欧元"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "被迫加息", "prob_density": 0.13,
             "triggers": ["核心通胀连续3月超预期"], "signals": ["ECB加息25bp"], "actions": ["加码EM空头(双收紧)"]},
        ]
    },

    "jpy_carry_unwind": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "利差维持", "prob_density": 0.01,
             "triggers": ["USD/JPY 157稳定"], "signals": ["JPY日波动"], "actions": ["不行动"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "低风险", "prob_density": 0.02,
             "triggers": ["VIX<25→carry安全"], "signals": ["VIX趋势"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "触发区 ★", "prob_density": 0.08,
             "triggers": ["美股-10%+VIX>30→2024.08重演"], "signals": ["USD/JPY日内>2%波动"], "actions": ["减杠杆"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "链式反应", "prob_density": 0.10,
             "triggers": ["carry平仓→全球去杠杆→EM资本外逃"], "signals": ["跨资产相关性飙升"], "actions": ["全面风控"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "新均衡", "prob_density": 0.09,
             "triggers": ["BOJ干预or利差收窄"], "signals": ["USD/JPY<150"], "actions": ["JPY多头"]},
        ],
        "dialectic": {
            "thesis": "平仓(30%): 2024.08先例——3天VIX从13到65,全球股市-10%。当前carry规模更大(>$4T)。只需VIX>30+美股-10%触发。",
            "antithesis": "不平仓(70%): USD/JPY 157高位=利差仍宽。BOJ不太可能在战时加息。2024.08很快恢复→市场学会了。需要极端恐慌才能触发。",
            "synthesis": "carry unwind是低概率高冲击事件('凸性炸弹')。不需要单独定价，但需要在风控中保留——VIX>30时自动减杠杆。",
            "revision_history": ["v1 0.30: 基于2024.08类比+当前carry规模"]
        }
    },

    "cny_controlled_depreciation": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "PBOC坚守", "prob_density": 0.02,
             "triggers": ["中间价6.9007"], "signals": ["离岸CNH"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "压力积累", "prob_density": 0.05,
             "triggers": ["油价→进口成本↑","资本流出初步"], "signals": ["外储月报"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "政策调整 ★", "prob_density": 0.10,
             "triggers": ["贸易顺差收窄+二级制裁风险"], "signals": ["PBOC中间价趋势"], "actions": ["做空CNH"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "有序贬值", "prob_density": 0.13,
             "triggers": ["PBOC允许滑向7.05-7.10"], "signals": ["中间价连续走弱"], "actions": ["加码"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "新均衡", "prob_density": 0.10,
             "triggers": ["7.0-7.15区间"], "signals": ["外储稳定"], "actions": ["锁利"]},
        ]
    },

    "euro_parity_risk": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "初始压力", "prob_density": 0.01,
             "triggers": ["EUR/USD 1.16"], "signals": ["EUR日波动"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "缓慢下行", "prob_density": 0.02,
             "triggers": ["能源成本差异(US自给vs EU依赖)"], "signals": ["EUR/USD趋势"], "actions": ["小仓做空EUR"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "加速", "prob_density": 0.05,
             "triggers": ["EU能源危机2.0确认"], "signals": ["EUR/USD<1.10"], "actions": ["加码"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "ECB困境 ★", "prob_density": 0.08,
             "triggers": ["ECB加息→但市场解读为'杀增长'→利空EUR"], "signals": ["EUR/USD<1.05"], "actions": ["target parity"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "测试平价", "prob_density": 0.09,
             "triggers": ["能源+ECB+难民三重压力"], "signals": ["EUR/USD<1.00"], "actions": ["获利了结"]},
            {"id": "w25_plus", "weeks": "W25+", "label": "结构性弱势", "prob_density": 0.05,
             "triggers": ["能源依赖+防务负担→长期弱势"], "signals": [""], "actions": [""]},
        ]
    },

    "wartime_capital_controls": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "初步限制", "prob_density": 0.05,
             "triggers": ["回购限制(LMT/RTX)"], "signals": ["行政命令"], "actions": ["军工股回调→买入"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "扩展", "prob_density": 0.10,
             "triggers": ["产能管制扩大?"], "signals": ["白宫与CEO会议"], "actions": ["评估受影响板块"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "能源管制 ★", "prob_density": 0.15,
             "triggers": ["汽油$5→出口限制?","DPA动用"], "signals": ["能源出口禁令?"], "actions": ["做空能源出口商"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "全面战时经济", "prob_density": 0.18,
             "triggers": ["如果>4月→更多行业管制"], "signals": ["国防生产法(DPA)广泛动用"], "actions": ["重估所有受管制板块"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "常态化", "prob_density": 0.12,
             "triggers": ["管制变成'新常态'"], "signals": [""], "actions": [""]},
        ]
    },

    "irgc_nuclear_acceleration": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "设施评估", "prob_density": 0.05,
             "triggers": ["B-2打击后→Fordow地下设施存活?"], "signals": ["IAEA紧急报告"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "教义解禁", "prob_density": 0.10,
             "triggers": ["哈梅内伊法令失效→IRGC决策"], "signals": ["伊朗核声明"], "actions": ["影响制裁判断"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "浓缩加速 ★", "prob_density": 0.15,
             "triggers": ["60%→90%仅需数周"], "signals": ["IAEA检查中断?"], "actions": ["做多黄金(核恐慌溢价)"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "武器化?", "prob_density": 0.12,
             "triggers": ["90%浓缩铀→武器化决策"], "signals": ["卫星图像(Fordow活动)"], "actions": ["极端避险"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "博弈均衡", "prob_density": 0.08,
             "triggers": ["核威慑形成→新博弈均衡"], "signals": ["US/以色列是否先发制人"], "actions": ["尾部风险定价"]},
        ],
        "dialectic": {
            "thesis": "加速(50%): 哈梅内伊的核禁令法令随他死亡失效。IRGC的生存逻辑=只有核武器才能防止再次被打击。Fordow地下设施可能幸存。60%→90%浓缩仅需数周。",
            "antithesis": "受阻(50%): B-2打击可能已摧毁关键设施。IAEA仍在监测(虽然受限)。核武器化需要弹头小型化技术(伊朗未验证)。核武加速会给美方提供升级借口。",
            "synthesis": "浓缩加速是高概率的,但从浓缩到实际武器化有技术鸿沟。最可能结果:伊朗达到'隐性核门槛'(有能力但不组装)——这本身就改变博弈结构。",
            "revision_history": ["v1 0.50: 基于生存逻辑vs技术约束的平衡判断"]
        }
    },

    "secondary_sanctions_wave": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "战争优先", "prob_density": 0.05,
             "triggers": ["军事行动优先于经济战"], "signals": ["OFAC公告"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "制裁升级 ★", "prob_density": 0.15,
             "triggers": ["UK/EU已宣布新制裁","Trump二级制裁威胁"], "signals": ["中国银行被制裁?"], "actions": ["做空中概股?"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "执行", "prob_density": 0.20,
             "triggers": ["打击中国/印度伊朗石油贸易"], "signals": ["中伊原油贸易数据"], "actions": ["影响CNY判断"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "反制", "prob_density": 0.15,
             "triggers": ["中国反制裁?","中美贸易紧张"], "signals": ["外交声明"], "actions": ["跟踪中美关系"]},
        ]
    },

    "trade_route_reshuffle": {
        "dialectic": {
            "thesis": "重组(68%): 多条路线已在执行(中印→俄油,美油→澳,Shell→哈萨克斯坦)。即使冲突结束,部分路线会固化(沉没成本+新合同)。",
            "antithesis": "有限(32%): 完全重组需要基础设施(管道/港口)——不是几个月能建的。市场价格机制会在冲突结束后拉回效率路线。",
            "synthesis": "短期重组是确定的(已在发生)。长期固化取决于冲突持续时间——>6个月→大部分重组不可逆; <2个月→大部分回归。",
            "revision_history": ["v1 0.85→v2 0.80→v3 0.68: 传导后调整"]
        }
    },

    "refugee_wave_europe": {
        "time_phases": [
            {"id": "w1_2", "weeks": "W1-2", "label": "境内流离", "prob_density": 0.01,
             "triggers": ["黎巴嫩83000+流离失所"], "signals": ["UNHCR数据"], "actions": ["观察"]},
            {"id": "w3_5", "weeks": "W3-5", "label": "路线形成", "prob_density": 0.02,
             "triggers": ["经土耳其/希腊路线激活"], "signals": ["地中海偷渡船数"], "actions": ["观察"]},
            {"id": "w6_10", "weeks": "W6-10", "label": "初步涌入", "prob_density": 0.05,
             "triggers": ["黎巴嫩+叙利亚难民"], "signals": ["希腊/意大利登陆数"], "actions": ["影响EU政治判断"]},
            {"id": "w11_16", "weeks": "W11-16", "label": "规模化", "prob_density": 0.10,
             "triggers": ["伊朗难民加入(如果内部崩溃)"], "signals": ["EU紧急峰会"], "actions": ["影响右翼政治判断"]},
            {"id": "w17_24", "weeks": "W17-24", "label": "政治化 ★", "prob_density": 0.12,
             "triggers": ["难民议题进入选举话语"], "signals": ["民调变化"], "actions": ["做空欧洲资产?"]},
        ]
    },
}

# Apply
tp_count = 0
di_count = 0
for nid, data in updates.items():
    if nid not in nodes:
        continue
    if "time_phases" in data:
        nodes[nid]["time_phases"] = data["time_phases"]
        # For state nodes, don't recalculate prob from phases (phases are qualitative)
        if nodes[nid].get("node_type") == "prediction":
            total = sum(p["prob_density"] for p in data["time_phases"])
            if total > 0:
                nodes[nid]["probability"] = round(total, 4)
        tp_count += 1
    if "dialectic" in data:
        nodes[nid]["dialectic"] = data["dialectic"]
        di_count += 1

dag["updated"] = datetime.now(timezone.utc).isoformat()
with open("data/dag.json", "w") as f:
    json.dump(dag, f, ensure_ascii=False, indent=2)

# Summary
total_tp = sum(1 for n in nodes.values() if n.get("time_phases"))
total_di = sum(1 for n in nodes.values() if n.get("dialectic"))
print(f"=== 全量注入完成 ===")
print(f"新增: {tp_count} 时间化 + {di_count} 辩证")
print(f"总计: {total_tp} 时间化 / {total_di} 辩证 / {len(nodes)} 节点")
print()

# Show coverage
for nid, n in sorted(nodes.items(), key=lambda x: -x[1]["probability"]):
    nt = n.get("node_type", "?")
    if nt == "event" and n["probability"] >= 0.95:
        continue
    tp = "⏱" if n.get("time_phases") else " "
    di = "⚖" if n.get("dialectic") else " "
    print(f"  {tp}{di} [{nt[:4]}] {n['probability']:.2f} | {n['label']}")
