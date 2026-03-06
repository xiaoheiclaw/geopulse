"""Seed the GeoPulse DAG with manually constructed initial state.

No LLM dependency — builds the DAG directly from GMF市场追踪 (3/2-3/5) data.
"""
from datetime import datetime, timezone

from geopulse.models import DAG, Edge, Event, Node
from geopulse.propagator import propagate
from geopulse.reporter import Reporter
from geopulse.storage import DAGStorage

NOW = datetime.now(timezone.utc)


def build_initial_dag() -> DAG:
    """Construct the initial DAG from GMF market tracking data (3/2-3/5)."""
    dag = DAG(scenario="us_iran_conflict", scenario_label="美伊冲突")

    # =========================================================================
    # NODES — organized by order (causal distance)
    # =========================================================================

    # --- 0阶：触发事件（已发生，prob ≈ 1.0）---
    nodes_0 = [
        Node(
            id="us_israel_strike_iran",
            label="美以联合空袭伊朗",
            domains=["军事"],
            probability=1.0, confidence=0.99,
            evidence=[
                "2/28'咆哮雄狮/史诗之怒'行动",
                "哈梅内伊等40-48名高级官员死亡",
                "截至3/5伊朗死亡超1045人",
                "超1700次打击，4000+枚炸弹",
            ],
            reasoning="事实节点：美以已对伊朗发动大规模空袭",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="iran_massive_retaliation",
            label="伊朗大规模报复（500+导弹/2000无人机）",
            domains=["军事"],
            probability=1.0, confidence=0.99,
            evidence=[
                "伊朗发射500+导弹2000架无人机",
                "打击以色列、美军基地及海湾国家",
                "迪拜/阿布扎比/巴林/科威特机场受损",
            ],
            reasoning="事实节点：伊朗已发动大规模报复",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="khamenei_killed",
            label="哈梅内伊遇袭身亡",
            domains=["政治", "军事"],
            probability=1.0, confidence=0.95,
            evidence=[
                "NYT/Reuters报道确认",
                "专家会议在IRGC压力下讨论继任",
            ],
            reasoning="事实节点：最高领袖死亡，伊朗权力真空",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="hormuz_blockade",
            label="霍尔木兹海峡事实封锁（通行量跌80-90%）",
            domains=["能源", "军事"],
            probability=1.0, confidence=0.95,
            evidence=[
                "通行量暴跌80-90%",
                "超200艘油气船抛锚或绕行",
                "6+商船受损，2-3名船员死亡",
                "GPS干扰和无人机威胁频发",
                "航运巨头暂停穿越",
            ],
            reasoning="事实节点：海峡已实质瘫痪",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="saudi_refinery_hit",
            label="沙特Ras Tanura炼油厂被击中关停",
            domains=["能源"],
            probability=1.0, confidence=0.95,
            evidence=["日处理55万桶炼油厂被无人机击中起火后关停"],
            reasoning="事实节点：沙特关键炼油设施受损",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="qatar_lng_halt",
            label="卡塔尔LNG全面停产（force majeure）",
            domains=["能源"],
            probability=1.0, confidence=0.95,
            evidence=["QatarEnergy宣布force majeure", "Ras Laffan LNG全面暂停"],
            reasoning="事实节点：全球最大LNG出口国停产",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="us_sub_sinks_iranian_ship",
            label="美潜艇击沉伊朗军舰（二战以来首次鱼雷攻击）",
            domains=["军事"],
            probability=1.0, confidence=0.90,
            evidence=["印度洋击沉伊朗护卫舰", "80+伊朗海军死亡", "32人被斯里兰卡海军救起"],
            reasoning="事实节点：美军二战以来首次鱼雷攻击",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="israel_invades_lebanon",
            label="以色列地面入侵黎巴嫩",
            domains=["军事"],
            probability=1.0, confidence=0.95,
            evidence=[
                "3/3授权地面入侵",
                "命令利塔尼河以南20万居民撤离",
                "小规模部队已进入南黎",
            ],
            reasoning="事实节点：以军已进入黎巴嫩",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="houthi_war_state",
            label="也门胡塞武装宣布进入战争状态",
            domains=["军事", "政治"],
            probability=1.0, confidence=0.90,
            evidence=["政治局宣布处于战争状态", "配合抵抗轴心协调行动"],
            reasoning="事实节点：胡塞加入战争",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="senate_rejects_war_limit",
            label="美参议院否决限制总统战争权力",
            domains=["政治"],
            probability=1.0, confidence=0.95,
            evidence=["参议院否决限制总统战争权力决议"],
            reasoning="事实节点：美国国内政治支持持续军事行动",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="iran_protests",
            label="伊朗爆发1979年以来最大规模抗议",
            domains=["社会", "政治"],
            probability=1.0, confidence=0.85,
            evidence=["经济崩溃恐慌引发大规模抗议", "互联网被封锁"],
            reasoning="事实节点：伊朗国内动荡",
            created=NOW, last_updated=NOW,
        ),
    ]

    # --- 1阶：直接后果 ---
    nodes_1 = [
        Node(
            id="iran_power_transition",
            label="伊朗权力交接：莫杰塔巴·哈梅内伊继位",
            domains=["政治"],
            probability=0.75, confidence=0.70,
            evidence=[
                "专家会议在IRGC压力下倾向莫杰塔巴（56岁，中级教士）",
                "临时领导委员会誓言'无情继续报复'",
                "拒绝与美国谈判",
            ],
            reasoning="IRGC主导下的继任最可能但尚未正式确认",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="conflict_spillover_gulf",
            label="冲突外溢至6个海湾国家",
            domains=["军事", "政治"],
            probability=1.0, confidence=0.95,
            evidence=[
                "迪拜/阿布扎比/巴林/科威特/卡塔尔/阿曼遭打击",
                "美驻利雅得大使馆被无人机击中",
                "阿塞拜疆纳赫奇万机场被击中",
                "NATO在土叙边境拦截伊朗导弹",
            ],
            reasoning="事实节点：冲突已远超美伊双边范围",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="oil_price_surge",
            label="油价飙升（Brent $77-82，涨6-13%）",
            domains=["金融", "能源"],
            probability=1.0, confidence=0.95,
            evidence=[
                "Brent短暂触及$82+",
                "WTI涨至$72-74",
                "亚洲炼油利润飙至4年新高$30/桶",
                "VLCC运费创纪录$423,736/天",
            ],
            reasoning="事实节点：能源价格已经飙升",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="global_shipping_paralysis",
            label="全球航空航运瘫痪",
            domains=["经济"],
            probability=1.0, confidence=0.95,
            evidence=[
                "中东机场航班大面积取消",
                "1100+船员滞留",
                "LNG航运费暴涨650%（4万→30万美元/天）",
                "阿曼Duqm港、杰贝阿里港遭袭",
            ],
            reasoning="事实节点：物流已严重中断",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="energy_trade_rerouting",
            label="全球能源贸易路线重组",
            domains=["能源", "经济"],
            probability=0.90, confidence=0.85,
            evidence=[
                "中国暂停新燃料出口合同",
                "俄罗斯2艘乌拉尔油轮转向印度",
                "Exxon首次从墨西哥湾运汽油到澳大利亚",
                "伊拉克停止库尔德斯坦石油出口",
            ],
            reasoning="多国已实际调整能源贸易路线",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="hezbollah_counterattack",
            label="真主党全面反击以色列",
            domains=["军事"],
            probability=1.0, confidence=0.90,
            evidence=["从黎巴嫩向以色列北部持续发射火箭"],
            reasoning="事实节点：真主党已发动报复",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="insurance_war_risk_cancelled",
            label="保险公司取消霍尔木兹海峡战争险",
            domains=["金融"],
            probability=1.0, confidence=0.90,
            evidence=["保险公司取消霍尔木兹海峡战争险"],
            reasoning="事实节点：航运保险市场已崩溃",
            created=NOW, last_updated=NOW,
        ),
    ]

    # --- 2阶：传导效应（预测） ---
    nodes_2 = [
        Node(
            id="oil_breaks_100",
            label="油价突破$100/桶",
            domains=["金融", "能源"],
            probability=0.65, confidence=0.70,
            evidence=[
                "StanChart上调油价预测至$74",
                "分析师预测若中断持续可能破$100",
                "当前Brent $77-82已逼近",
            ],
            reasoning="海峡封锁+沙特/卡塔尔供应中断组合效应，若持续2周以上大概率破百",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="us_ground_troops_iran",
            label="美军地面部队入伊朗",
            domains=["军事", "政治"],
            probability=0.35, confidence=0.55,
            evidence=[
                "特朗普不排除boots on the ground",
                "Hegseth称just getting started",
                "预计行动持续4-5周",
                "CIA已武装库尔德武装准备地面行动",
            ],
            reasoning="空中行动4-5周内可能不足以达成所有目标，但地面战争政治风险极高",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="japan_spr_release",
            label="日本释放战略石油储备",
            domains=["能源", "政治"],
            probability=0.80, confidence=0.75,
            evidence=["日本炼油商95%原油来自中东", "已呼吁释放战略储备"],
            reasoning="日本对中东原油依赖度最高，几乎必然释放SPR",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="gulf_alliance_fracture",
            label="海湾国家联盟分裂",
            domains=["政治"],
            probability=0.55, confidence=0.60,
            evidence=[
                "西班牙拒绝美国使用联合基地",
                "巴基斯坦在公众舆论和地缘关系间左右为难",
                "海湾平民区遭导弹碎片影响",
            ],
            reasoning="海湾国家平民受波及可能导致对美支持动摇",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="nato_limited_intervention",
            label="NATO有限军事介入",
            domains=["军事", "政治"],
            probability=0.40, confidence=0.55,
            evidence=[
                "NATO在土叙边境拦截伊朗导弹",
                "西班牙拒绝=盟国分歧",
            ],
            reasoning="NATO已被动介入拦截，但主动参战概率低",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="iran_nuclear_acceleration",
            label="伊朗核计划加速",
            domains=["军事", "科技"],
            probability=0.50, confidence=0.55,
            evidence=["核设施在空袭中受损", "但可能刺激残余力量加速"],
            reasoning="空袭可能摧毁部分设施但也可能加速地下核计划",
            created=NOW, last_updated=NOW,
        ),
    ]

    # --- 3阶：深层连锁（预测） ---
    nodes_3 = [
        Node(
            id="global_energy_crisis",
            label="全球能源危机（供应缺口持续超2周）",
            domains=["能源", "经济"],
            probability=0.70, confidence=0.65,
            evidence=[
                "霍尔木兹海峡封锁+沙特+卡塔尔三重打击",
                "全球20%石油供应受威胁",
                "恢复至少需要1个月",
            ],
            reasoning="三大供应中断同时发生，短期替代困难",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="global_recession_risk",
            label="全球经济衰退风险上升",
            domains=["经济", "金融"],
            probability=0.45, confidence=0.50,
            evidence=["能源危机+供应链中断+金融市场恐慌组合效应"],
            reasoning="若油价持续$100+超过1个月，全球GDP增长可能转负",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="iran_regime_change",
            label="伊朗政权更迭",
            domains=["政治", "社会"],
            probability=0.25, confidence=0.40,
            evidence=[
                "最大规模抗议+领导层被击杀",
                "但IRGC仍控制局势",
            ],
            reasoning="IRGC控制力强，短期政权更迭概率低但中期不可排除",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="regional_war",
            label="中东区域性全面战争",
            domains=["军事", "政治"],
            probability=0.55, confidence=0.55,
            evidence=[
                "冲突已扩至以色列-黎巴嫩、也门、6个海湾国家",
                "胡塞+真主党+伊朗联合作战",
                "叙利亚极端分子在黎巴嫩边境集结",
            ],
            reasoning="多战线同时激活，抵抗轴心协调行动，区域战争正在形成",
            created=NOW, last_updated=NOW,
        ),
        Node(
            id="china_russia_strategic_shift",
            label="中俄战略立场转变",
            domains=["政治"],
            probability=0.20, confidence=0.45,
            evidence=[
                "俄中谴责但拒绝军事支持",
                "中国卫星提供情报作为'沉默盾牌'",
            ],
            reasoning="中俄维持谴责+暗中支持的灰色地带，全面转向概率低",
            created=NOW, last_updated=NOW,
        ),
    ]

    # Add all nodes
    for node in nodes_0 + nodes_1 + nodes_2 + nodes_3:
        dag.nodes[node.id] = node

    # =========================================================================
    # EDGES — causal relationships with weights
    # =========================================================================
    edges = [
        # 0阶 → 1阶
        Edge(source="us_israel_strike_iran", target="iran_massive_retaliation",
             weight=0.95, reasoning="空袭直接触发伊朗报复"),
        Edge(source="us_israel_strike_iran", target="khamenei_killed",
             weight=0.90, reasoning="空袭导致最高领袖死亡"),
        Edge(source="khamenei_killed", target="iran_power_transition",
             weight=0.90, reasoning="最高领袖死亡必然引发权力交接"),
        Edge(source="khamenei_killed", target="iran_protests",
             weight=0.70, reasoning="领导层被击杀+经济崩溃恐慌引发抗议"),
        Edge(source="iran_massive_retaliation", target="conflict_spillover_gulf",
             weight=0.90, reasoning="伊朗报复打击扩至多个海湾国家"),
        Edge(source="iran_massive_retaliation", target="hormuz_blockade",
             weight=0.85, reasoning="伊朗报复中封锁海峡"),
        Edge(source="iran_massive_retaliation", target="saudi_refinery_hit",
             weight=0.80, reasoning="无人机打击沙特炼油设施"),
        Edge(source="hormuz_blockade", target="qatar_lng_halt",
             weight=0.85, reasoning="海峡封锁导致卡塔尔LNG无法出口"),
        Edge(source="hormuz_blockade", target="oil_price_surge",
             weight=0.90, reasoning="全球20%石油供应通道中断推高油价"),
        Edge(source="hormuz_blockade", target="global_shipping_paralysis",
             weight=0.90, reasoning="海峡瘫痪导致航运全面中断"),
        Edge(source="hormuz_blockade", target="insurance_war_risk_cancelled",
             weight=0.85, reasoning="海峡高危导致保险公司撤出"),
        Edge(source="saudi_refinery_hit", target="oil_price_surge",
             weight=0.75, reasoning="日产55万桶炼油厂关停推高油价"),
        Edge(source="qatar_lng_halt", target="oil_price_surge",
             weight=0.70, reasoning="LNG停产推高整体能源价格"),
        Edge(source="israel_invades_lebanon", target="hezbollah_counterattack",
             weight=0.95, reasoning="以色列入侵直接触发真主党反击"),
        Edge(source="senate_rejects_war_limit", target="us_ground_troops_iran",
             weight=0.50, reasoning="国会放行降低地面战争政治阻力"),

        # 1阶 → 2阶
        Edge(source="oil_price_surge", target="oil_breaks_100",
             weight=0.70, reasoning="当前$77-82，持续中断将推至$100+"),
        Edge(source="oil_price_surge", target="energy_trade_rerouting",
             weight=0.80, reasoning="高油价+断供推动贸易路线重组"),
        Edge(source="global_shipping_paralysis", target="energy_trade_rerouting",
             weight=0.75, reasoning="航运瘫痪加速替代路线形成"),
        Edge(source="conflict_spillover_gulf", target="gulf_alliance_fracture",
             weight=0.65, reasoning="平民受波及导致海湾国家立场分化"),
        Edge(source="conflict_spillover_gulf", target="nato_limited_intervention",
             weight=0.50, reasoning="冲突扩大可能触发NATO介入"),
        Edge(source="iran_power_transition", target="iran_nuclear_acceleration",
             weight=0.55, reasoning="新强硬领导层可能加速核计划"),
        Edge(source="us_israel_strike_iran", target="iran_nuclear_acceleration",
             weight=0.45, reasoning="核设施受损但可能刺激地下加速"),
        Edge(source="insurance_war_risk_cancelled", target="oil_breaks_100",
             weight=0.55, reasoning="无保险→运费暴涨→推高终端油价"),
        Edge(source="houthi_war_state", target="regional_war",
             weight=0.65, reasoning="胡塞参战扩大战争范围"),
        Edge(source="hezbollah_counterattack", target="regional_war",
             weight=0.70, reasoning="黎以战线激活加剧区域战争"),
        # 2阶 → 3阶
        Edge(source="oil_breaks_100", target="global_energy_crisis",
             weight=0.80, reasoning="$100+油价意味着供应严重不足"),
        Edge(source="energy_trade_rerouting", target="global_energy_crisis",
             weight=0.60, reasoning="路线重组增加运输成本和时间"),
        Edge(source="global_energy_crisis", target="global_recession_risk",
             weight=0.70, reasoning="能源危机是衰退的核心驱动因素"),
        Edge(source="global_shipping_paralysis", target="global_recession_risk",
             weight=0.55, reasoning="供应链中断拖累全球经济"),
        Edge(source="us_ground_troops_iran", target="regional_war",
             weight=0.80, reasoning="地面入侵将全面升级为区域战争"),
        Edge(source="iran_protests", target="iran_regime_change",
             weight=0.50, reasoning="大规模抗议是政权更迭的前置条件"),
        Edge(source="iran_power_transition", target="iran_regime_change",
             weight=0.30, reasoning="权力交接混乱可能演变为政权更迭"),
        Edge(source="gulf_alliance_fracture", target="china_russia_strategic_shift",
             weight=0.35, reasoning="西方联盟松动给中俄创造空间"),
        Edge(source="regional_war", target="global_recession_risk",
             weight=0.60, reasoning="区域战争加剧经济恐慌"),
    ]

    dag.edges = edges
    return dag


def build_seed_events() -> list[Event]:
    """Create event records for logging purposes."""
    return [
        Event(headline="美以联合空袭伊朗", details="2/28'咆哮雄狮'行动，1700+打击，哈梅内伊死亡，1045+死亡",
              domains=["军事"], significance=5, source_url="GMF市场追踪"),
        Event(headline="伊朗500+导弹/2000无人机报复", details="打击以色列、美军基地及6个海湾国家",
              domains=["军事"], significance=5, source_url="GMF市场追踪"),
        Event(headline="霍尔木兹海峡事实封锁", details="通行量跌80-90%，200+船滞留",
              domains=["能源", "军事"], significance=5, source_url="GMF市场追踪"),
        Event(headline="沙特Ras Tanura炼油厂关停", details="日产55万桶，无人机击中起火",
              domains=["能源"], significance=5, source_url="GMF市场追踪+OilPrice"),
        Event(headline="卡塔尔LNG全面停产", details="Ras Laffan LNG暂停，宣布force majeure",
              domains=["能源"], significance=5, source_url="GMF市场追踪+OilPrice"),
        Event(headline="油价飙升Brent $77-82", details="WTI $72-74，VLCC $423K/天，LNG运费涨650%",
              domains=["金融", "能源"], significance=4, source_url="GMF市场追踪+CNBC"),
        Event(headline="以色列地面入侵黎巴嫩", details="3/3授权，20万人撤离，真主党反击",
              domains=["军事"], significance=5, source_url="GMF市场追踪"),
        Event(headline="冲突外溢至6个海湾国家", details="迪拜/阿布扎比/巴林/科威特/卡塔尔/阿曼遭打击",
              domains=["军事", "政治"], significance=5, source_url="GMF市场追踪"),
        Event(headline="伊朗爆发1979年以来最大抗议", details="经济崩溃恐慌引发，互联网封锁",
              domains=["社会", "政治"], significance=4, source_url="GMF市场追踪+Al Jazeera"),
        Event(headline="美潜艇击沉伊朗军舰", details="二战以来首次鱼雷攻击，80+海军死亡",
              domains=["军事"], significance=4, source_url="The Cradle"),
    ]


def main():
    # Build DAG
    dag = build_initial_dag()
    print(f"构建完成: {len(dag.nodes)} 节点, {len(dag.edges)} 边")

    assert not dag.has_cycle(), "DAG has cycle!"
    print("无环校验: ✓")

    # Propagate
    propagated = propagate(dag)

    # Save
    storage = DAGStorage(data_dir="data")
    storage.save(propagated)
    print(f"已保存 (version {propagated.version})")

    # Log events
    events = build_seed_events()
    events_log = storage.data_dir / "events.jsonl"
    events_log.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(events_log, "w", encoding="utf-8") as f:
        for ev in events:
            entry = ev.model_dump(mode="json")
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"已写入 {len(events)} 条事件日志")

    # Report
    reporter = Reporter()
    report = reporter.daily_report(
        propagated,
        events_summary=[e.headline for e in events],
    )
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
