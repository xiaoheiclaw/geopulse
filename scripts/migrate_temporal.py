"""Migrate key DAG nodes to temporal probability + dialectic reasoning."""
import json
from datetime import datetime, timezone

dag = json.load(open("data/dag.json"))
nodes = dag["nodes"]

# =================================================================
# TEMPORAL PROBABILITY: distribute scalar prob across time phases
# =================================================================

temporal_nodes = {
    "conflict_duration_over_2m": {
        "time_phases": [
            {"id": "w1_2", "label": "冲击期", "weeks": "W1-2", "prob_density": 0.02,
             "triggers": ["初始打击+报复循环"], "signals": ["伊朗报复规模"], "actions": ["观察，不行动"]},
            {"id": "w3_5", "label": "Trump时间表窗口", "weeks": "W3-5", "prob_density": 0.08,
             "triggers": ["Trump 4-5周时间表到期", "斋月结束", "胡塞决策:重启红海?"],
             "signals": ["Trump措辞软化?", "胡塞是否激活", "首批商船通过霍尔木兹?"],
             "actions": ["强制审视", "3信号任一出现→评估减仓"]},
            {"id": "w6_10", "label": "第一消耗期 ★", "weeks": "W6-10", "prob_density": 0.25,
             "triggers": ["SPR/库存耗尽临界(韩国LNG 9天)", "汽油破$4→政治问题", "第三方调解压力汇合"],
             "signals": ["油价二元分布:被迫打下来 or 破$100加速"],
             "actions": ["期权替代方向性头寸", "做多波动率>做多方向"]},
            {"id": "w11_16", "label": "疲劳/升级分叉 ★", "weeks": "W11-16", "prob_density": 0.28,
             "triggers": ["双方弹药/无人机消耗评估", "Mojtaba权力巩固度→能签协议?", "代理人全面激活?"],
             "signals": ["通胀传导进实体", "Fed困境进决策期"],
             "actions": ["疲劳降级→平能源多头,保防务+黄金", "升级→加码通胀(TIPS,大宗)"]},
            {"id": "w17_24", "label": "深度消耗", "weeks": "W17-24", "prob_density": 0.22,
             "triggers": ["国内政治压力累积", "拦截弹库存vs无人机产能", "全球供应链二次冲击"],
             "signals": ["从能源/避险转向通胀主线"],
             "actions": ["空成长,多TIPS/大宗/浮动利率"]},
            {"id": "w25_plus", "label": "长尾", "weeks": "W25+", "prob_density": 0.15,
             "triggers": ["政权实质变化或结构性僵局"],
             "signals": ["从事件交易转结构性重配"],
             "actions": ["防务超级周期核心多头"]}
        ]
    },
    "oil_price_100_breach": {
        "time_phases": [
            {"id": "w1_2", "label": "冲击期", "weeks": "W1-2", "prob_density": 0.05,
             "triggers": ["恐慌溢价"], "signals": ["Brent日内波动>5%"], "actions": ["观察"]},
            {"id": "w3_5", "label": "Trump窗口", "weeks": "W3-5", "prob_density": 0.10,
             "triggers": ["护航计划执行效果"], "signals": ["首批商船通过?"], "actions": ["护航成功→做空油价"]},
            {"id": "w6_10", "label": "第一消耗期 ★", "weeks": "W6-10", "prob_density": 0.20,
             "triggers": ["SPR耗尽", "沙特Aramco遭击?"], "signals": ["库存数据周报"],
             "actions": ["破$100→做多通胀链(化肥→粮食→EM)"]},
            {"id": "w11_16", "label": "分叉期", "weeks": "W11-16", "prob_density": 0.10,
             "triggers": ["降级or升级决定油价中枢"], "signals": ["OPEC+紧急会议?"], "actions": ["根据分叉方向调整"]},
            {"id": "w17_24", "label": "深度消耗", "weeks": "W17-24", "prob_density": 0.05,
             "triggers": ["结构性溢价固化"], "signals": ["远月contango结构"], "actions": ["锁利"]},
        ]
    },
    "global_stagflation_risk": {
        "time_phases": [
            {"id": "w1_2", "label": "冲击期", "weeks": "W1-2", "prob_density": 0.0,
             "triggers": [], "signals": [], "actions": ["太早,不行动"]},
            {"id": "w3_5", "label": "Trump窗口", "weeks": "W3-5", "prob_density": 0.02,
             "triggers": ["通胀预期初步上移"], "signals": ["breakeven利率"], "actions": ["观察TIPS"]},
            {"id": "w6_10", "label": "第一消耗期", "weeks": "W6-10", "prob_density": 0.08,
             "triggers": ["油价持续>$95→CPI传导开始"], "signals": ["核心CPI环比"], "actions": ["建仓TIPS"]},
            {"id": "w11_16", "label": "分叉期 ★", "weeks": "W11-16", "prob_density": 0.15,
             "triggers": ["通胀传导进实体经济", "GDP增速放缓信号"], "signals": ["PMI, 消费者信心"],
             "actions": ["空高估值成长,多大宗生产商"]},
            {"id": "w17_24", "label": "深度消耗 ★", "weeks": "W17-24", "prob_density": 0.15,
             "triggers": ["Fed被迫表态", "企业盈利下修"], "signals": ["FOMC声明措辞变化"],
             "actions": ["全面通胀对冲"]},
            {"id": "w25_plus", "label": "长尾", "weeks": "W25+", "prob_density": 0.05,
             "triggers": ["结构性滞胀"], "signals": ["工资-物价螺旋?"], "actions": ["长期重配"]}
        ]
    },
    "em_currency_crisis": {
        "time_phases": [
            {"id": "w1_2", "label": "冲击期", "weeks": "W1-2", "prob_density": 0.01,
             "triggers": ["初始恐慌"], "signals": ["INR/TRY/EGP日波动"], "actions": ["太早"]},
            {"id": "w3_5", "label": "Trump窗口", "weeks": "W3-5", "prob_density": 0.02,
             "triggers": ["美元走强+资本外流初步"], "signals": ["DXY趋势"], "actions": ["观察"]},
            {"id": "w6_10", "label": "第一消耗期", "weeks": "W6-10", "prob_density": 0.05,
             "triggers": ["油价持续→进口成本飙升", "粮价上涨→补贴压力"], "signals": ["外储月报"],
             "actions": ["做空最脆弱EM货币"]},
            {"id": "w11_16", "label": "分叉期 ★", "weeks": "W11-16", "prob_density": 0.10,
             "triggers": ["carry unwind", "信贷紧缩传导"], "signals": ["主权CDS走阔"],
             "actions": ["加码EM空头"]},
            {"id": "w17_24", "label": "深度消耗 ★", "weeks": "W17-24", "prob_density": 0.12,
             "triggers": ["主权违约/资本管制"], "signals": ["IMF紧急贷款?"], "actions": ["高凸性tail hedge"]},
            {"id": "w25_plus", "label": "长尾", "weeks": "W25+", "prob_density": 0.05,
             "triggers": ["结构性重组"], "signals": [""], "actions": [""]}
        ]
    },
    "hormuz_blockade_de_facto": {
        "dialectic": {
            "thesis": "支持持续封锁(70%)：霍尔木兹已事实关闭6天；保险撤离+商船恐惧+USV威胁构成'自动升级机器'——无需单一行为者主动封锁，海峡就事实关闭。伊朗弹道导弹虽-90%，但USV/水雷/无人机成本极低(Shahed $35K vs 拦截弹$1-3M)，消耗战对美方不可持续。",
            "antithesis": "支持松动(30%)：美方护航承诺已导致亚洲LNG价格回落；伊朗攻击频次-90%降低实际威胁；Trump承诺政治风险保险为船东；恢复不需要伊朗合作——只需足够护航+保险替代。但关键缺陷：霍尔木兹是涌现式关闭(保险+恐惧+USV)，不是开关式。即使伊朗宣布开放→保险恢复承保→商船先行者→足够安全案例——多层协调博弈。",
            "synthesis": "霍尔木兹是'有缺陷但存在的焦点'——它具备突出性、可观测性、互损性、交易空间，但恢复机制是多层协调问题而非二元开关。30天持续概率70%，但概率分布不均：W1-5几乎确定持续，W6-10是关键——护航计划的执行效果在此窗口可验证。",
            "revision_history": [
                "v1 0.95: 初始种子DAG,当作确认事实",
                "v2 0.75: 节点类型改造,区分事件vs状态",
                "v3 0.70: 美方护航计划+导弹攻击↓→下调"
            ]
        }
    },
    "us_iran_ground_war": {
        "dialectic": {
            "thesis": "支持地面战(30%)：regime change目标需要地面控制；空中打击无法实现政权更迭(利比亚/阿富汗先例)；CIA代理人可能不足以推翻IRGC。",
            "antithesis": "反对地面战(70%)：伊朗面积4倍于伊拉克，扎格罗斯山脉天然屏障；CIA库尔德代理人路线是替代方案而非前奏；Iraq教训仍在(政治成本)；Trump'4-5周'暗示不想长期投入。",
            "synthesis": "CIA代理人+空中打击是'够用但不完美'的方案。大规模地面入侵需要Trump明确的政治意愿突变(当前无信号)。30%概率反映的是代理人路线失败后的升级风险。",
            "revision_history": [
                "v1 0.65: 初始过高,未考虑代理人替代",
                "v2 0.45: 红队审计下调",
                "v3 0.35: CIA代理人激活后进一步下调",
                "v4 0.30: 节点类型改造,显式判断"
            ]
        }
    }
}

# Apply to DAG
for nid, updates in temporal_nodes.items():
    if nid not in nodes:
        continue
    if "time_phases" in updates:
        nodes[nid]["time_phases"] = updates["time_phases"]
        # Recalculate aggregate probability from phases
        total = sum(p["prob_density"] for p in updates["time_phases"])
        nodes[nid]["probability"] = round(total, 4)
    if "dialectic" in updates:
        nodes[nid]["dialectic"] = updates["dialectic"]

dag["updated"] = datetime.now(timezone.utc).isoformat()

with open("data/dag.json", "w") as f:
    json.dump(dag, f, ensure_ascii=False, indent=2)

# Report
phased = sum(1 for n in nodes.values() if n.get("time_phases"))
dialectic = sum(1 for n in nodes.values() if n.get("dialectic"))
print(f"=== 时间化+辩证改造完成 ===")
print(f"时间化节点: {phased}")
print(f"辩证推理节点: {dialectic}")
print()
for nid in temporal_nodes:
    if nid in nodes:
        n = nodes[nid]
        phases = n.get("time_phases", [])
        if phases:
            total = sum(p["prob_density"] for p in phases)
            print(f"  {n['label']}: P={total:.0%}")
            for p in phases:
                bar = "█" * int(p["prob_density"] * 50) + "░" * (10 - int(p["prob_density"] * 50))
                print(f"    {p['weeks']:>6} {bar} {p['prob_density']:.0%} | {p.get('actions',[''])[0][:40]}")
        dia = n.get("dialectic")
        if dia:
            print(f"  {n['label']}: 辩证 ✓")
            print(f"    正: {dia['thesis'][:60]}...")
            print(f"    反: {dia['antithesis'][:60]}...")
            print(f"    合: {dia['synthesis'][:60]}...")
