"""Seed the GeoPulse DAG with recent news from RSS feeds via LLM analysis."""
import os

import anthropic

from geopulse.analyzer import EventAnalyzer
from geopulse.dag_engine import DAGEngine
from geopulse.models import DAG, Event
from geopulse.propagator import propagate
from geopulse.reporter import Reporter
from geopulse.storage import DAGStorage

PROXY = "http://127.0.0.1:59527"
API_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "") or None
MODEL = "claude-sonnet-4-5-20250929"

# Compiled from GMF市场追踪 (3/2, 3/4, 3/5) + RSS feeds (Al Jazeera, The Cradle, OilPrice)
# Organized by domain to ensure broad DAG coverage
SEED_ARTICLES = [
    # === 军事 ===
    {"title": "美以联合空袭伊朗：哈梅内伊遇袭身亡，死亡超1000人",
     "summary": "2月28日美以发动'咆哮雄狮/史诗之怒'行动，打击伊朗领导层、核设施和军事设施。最高领袖哈梅内伊等40-48名高级官员死亡。截至3月5日伊朗死亡超1045人含180+平民儿童。美以已发动超1700次打击，投掷4000+枚炸弹。美军6人阵亡18+重伤。以色列11-12人死亡数百伤。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "伊朗大规模报复：500+导弹2000架无人机，打击范围扩至海湾国家",
     "summary": "伊朗对以色列、美军基地及海湾国家发动报复。打击波及迪拜国际机场（航站楼损毁）、阿布扎比机场、巴林机场、科威特机场。沙特Ras Tanura炼油厂(日产55万桶)被无人机击中起火关停。迪拜/巴林住宅区受损。阿联酋3-4死、巴林1死。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "特朗普称战斗将持续4-5周，不排除地面部队入伊朗",
     "summary": "特朗普：行动将持续直到所有目标达成，预计4-5周。已击沉9艘伊朗军舰、摧毁海军总部。不排除派地面部队boots on the ground。国防部长Hegseth称just getting started。参议院否决限制总统战争权力。美国正快速增兵含航母F-35。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "以色列地面入侵黎巴嫩，真主党全面反击",
     "summary": "以色列3月3日授权地面入侵黎巴嫩，命令利塔尼河以南20万居民撤离。以军小规模部队已进入南黎打击真主党目标。真主党从黎巴嫩向以色列北部持续发射火箭报复。黎巴嫩新增数十死亡。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "美国潜艇击沉伊朗军舰，二战以来首次鱼雷攻击",
     "summary": "美军潜艇在印度洋/斯里兰卡附近击沉伊朗护卫舰，至少80名伊朗海军人员死亡，32人被斯里兰卡海军救起。这是二战以来美军首次鱼雷攻击。",
     "source_url": "The Cradle", "category": "rss"},
    # === 能源 ===
    {"title": "霍尔木兹海峡瘫痪第5天：通行量暴跌80-90%，200+船滞留",
     "summary": "海峡通行量暴跌80-90%，超200艘油气船抛锚或绕行。IRGC重申海峡关闭。至少6+艘商船/油轮受损，2-3名船员死亡。GPS干扰和无人机威胁频发。特朗普提出美海军护航+政治风险保险。但伊朗海军副司令称并未封锁海峡。航运巨头暂停穿越。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "沙特Ras Tanura炼油厂关停+卡塔尔LNG全面停产",
     "summary": "沙特Ras Tanura炼油厂(日处理55万桶)被伊朗无人机击中起火后关停。卡塔尔Ras Laffan LNG全面暂停(QatarEnergy宣布force majeure)。专家估计至少一个月恢复。全球LNG航运费暴涨650%从4万到30万美元/天。",
     "source_url": "GMF市场追踪+OilPrice", "category": "analysis"},
    {"title": "全球能源贸易路线重组：中国停出口、日本释放储备、俄油转向印度",
     "summary": "中国下令暂停新燃料出口合同。日本炼油商(95%原油来自中东)呼吁释放战略石油储备。俄罗斯2艘乌拉尔油轮(1400万桶)转向印度港口。Exxon首次从美国墨西哥湾运汽油到澳大利亚。伊拉克停止库尔德斯坦石油出口。",
     "source_url": "OilPrice+GMF", "category": "analysis"},
    # === 金融 ===
    {"title": "油价飙升：Brent触及$82+，保险战险取消，航运成本暴增",
     "summary": "Brent短暂触及$82+，结算约$77-82(涨6-13%)。WTI涨至$72-74。亚洲炼油利润飙至4年新高$30/桶。VLCC运费创纪录$423,736/天。保险公司取消霍尔木兹海峡战争险。StanChart上调油价预测至$74。分析师预测若中断持续油价可能破$100。",
     "source_url": "GMF市场追踪+CNBC", "category": "analysis"},
    # === 政治 ===
    {"title": "伊朗权力交接：莫杰塔巴·哈梅内伊在IRGC压力下继位",
     "summary": "NYT/Reuters/Iran International报道专家会议在IRGC压力下倾向莫杰塔巴·哈梅内伊(56岁,哈梅内伊次子,中级教士,与IRGC关系密切)为新最高领袖。伊朗官方尚未正式确认。临时领导委员会誓言'无情继续报复'、拒绝与美国谈判。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "冲突外溢：伊朗打击扩至6个海湾国家，NATO拦截导弹",
     "summary": "伊朗报复打击扩至迪拜、阿布扎比、巴林、科威特、卡塔尔、阿曼。美国驻利雅得大使馆被无人机击中起火。迪拜美领馆附近遭袭。NATO在土叙边境拦截伊朗导弹。阿塞拜疆纳赫奇万机场被无人机击中。冲突已远超美伊双边范围。",
     "source_url": "GMF市场追踪", "category": "analysis"},
    {"title": "俄中保持距离，西方内部分歧：西班牙拒绝美国使用基地",
     "summary": "俄罗斯和中国谴责美以但拒绝提供军事支持。中国卫星提供情报作为'沉默盾牌'。西班牙首相拒绝美国使用联合基地打击伊朗，特朗普威胁切断贸易。巴基斯坦在公众舆论和地缘关系间左右为难。",
     "source_url": "Al Jazeera+The Cradle", "category": "analysis"},
    # === 社会 ===
    {"title": "伊朗爆发1979年以来最大规模抗议，海湾平民恐慌",
     "summary": "伊朗内部爆发自1979年以来最大规模抗议(源于冲突导致的经济崩溃恐慌)。迪拜/巴林等地住宅区受导弹碎片影响，平民恐慌。海湾国家航空贸易严重中断。中东体育赛事(F1/Finalissima)取消，球员滞留。伊朗互联网被封锁。",
     "source_url": "GMF市场追踪+Al Jazeera", "category": "analysis"},
    # === 经济/科技 ===
    {"title": "全球航空航运瘫痪：中东机场关闭、1100+船员滞留",
     "summary": "迪拜/阿布扎比/巴林/科威特机场航班大面积取消空域关闭。海峡附近1100+船员滞留含韩国和印度油轮。港口(阿曼Duqm港、迪拜杰贝阿里港)遭袭。全球供应链物流面临数周中断风险。",
     "source_url": "GMF市场追踪+OilPrice", "category": "analysis"},
    {"title": "也门胡塞武装宣布进入战争状态，CIA武装库尔德武装",
     "summary": "也门胡塞武装政治局宣布处于战争状态,准备配合抵抗轴心协调行动。美国CIA武装库尔德武装准备在伊朗境内地面行动。伊朗威胁对伊拉克库尔德领导人直接打击。叙利亚极端分子军队在黎巴嫩边境集结。",
     "source_url": "The Cradle+Al Jazeera", "category": "analysis"},
]


def main():
    print(f"Seed articles: {len(SEED_ARTICLES)}")

    client_kwargs: dict = {"api_key": API_KEY}
    if BASE_URL:
        client_kwargs["base_url"] = BASE_URL
    if PROXY:
        import httpx
        client_kwargs["http_client"] = httpx.Client(proxy=PROXY)

    # Step 1: Extract events
    analyzer = EventAnalyzer(api_key=API_KEY, model=MODEL, proxy=PROXY, base_url=BASE_URL)

    all_events: list[Event] = []
    for i, article in enumerate(SEED_ARTICLES):
        print(f"  Analyzing [{i+1}/{len(SEED_ARTICLES)}] {article['title'][:60]}...")
        try:
            events = analyzer.analyze(article)
            all_events.extend(events)
            print(f"    -> {len(events)} events")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    print(f"\nTotal events extracted: {len(all_events)}")

    if not all_events:
        print("No events extracted, aborting.")
        return

    # Step 2: Build DAG
    dag = DAG(scenario="us_iran_conflict", scenario_label="美伊冲突")
    dag_engine = DAGEngine(api_key=API_KEY, model=MODEL, proxy=PROXY, base_url=BASE_URL)

    print("\nBuilding DAG from events...")
    updated_dag = dag_engine.update(dag, all_events)
    print(f"  Nodes: {len(updated_dag.nodes)}, Edges: {len(updated_dag.edges)}")

    # Step 3: Propagate
    propagated_dag = propagate(updated_dag)

    # Step 4: Save
    storage = DAGStorage(data_dir="data")
    storage.save(propagated_dag)
    print(f"  DAG saved (version {propagated_dag.version})")

    # Step 5: Report
    reporter = Reporter()
    analysis = getattr(updated_dag, "_analysis", "")
    insights = getattr(updated_dag, "_model_insights", [])
    events_summary = [e.headline for e in all_events[:10]]

    report = reporter.daily_report(
        propagated_dag,
        events_summary=events_summary,
        old_dag=None,
        analysis=analysis,
        model_insights=insights,
    )
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
