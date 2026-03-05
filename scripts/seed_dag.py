"""Seed the GeoPulse DAG with recent news from RSS feeds."""
import os

import anthropic

from geopulse.analyzer import EventAnalyzer
from geopulse.dag_engine import DAGEngine
from geopulse.models import DAG, Event
from geopulse.propagator import propagate
from geopulse.reporter import Reporter
from geopulse.storage import DAGStorage

PROXY = "http://127.0.0.1:7890"
API_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
MODEL = "claude-sonnet-4-5-20250929"

# Key events from past 7 days (Feb 28 - Mar 5, 2026), compiled from:
# Al Jazeera, The Cradle, OilPrice.com, Reuters, War on the Rocks
SEED_ARTICLES = [
    {"title": "US and Israel launch massive strikes on Iran, Supreme Leader Khamenei killed",
     "summary": "On Feb 28, Israel and the United States began Operation Roaring Lion/Epic Fury, striking Iran's leadership, nuclear sites, and military facilities. Supreme Leader Khamenei was killed along with several senior officials. Death toll reaches 787.",
     "source_url": "https://aljazeera.com", "category": "rss"},
    {"title": "Iran launches massive retaliation with 500+ ballistic missiles and 2000 drones",
     "summary": "Iran responded with unprecedented counter-strikes against Israel, US military bases in the region, and Arab states hosting US forces. Hundreds of missiles and drones targeted energy infrastructure and diplomatic compounds. US racks up billions in losses.",
     "source_url": "https://thecradle.co", "category": "rss"},
    {"title": "Strait of Hormuz shut down, 5 tankers damaged, shipping halted",
     "summary": "Shipping through Strait of Hormuz ground to near halt. 5 tankers damaged, 2 crew killed, 150 ships stranded. Insurance companies cancel war coverage. VLCC freight rates hit all-time high $423,736/day. Oil tanker hit by blast near Kuwait.",
     "source_url": "https://oilprice.com", "category": "rss"},
    {"title": "Oil prices surge 8-13%, analysts forecast $100+/barrel",
     "summary": "Brent jumped 9% to $79.45, WTI rose 8.4% to $72.74. StanChart hikes forecast to $74. Asia refining margins soar to 4-year high $30/barrel. Japan urges release of strategic reserves. China halts fuel exports amid global squeeze.",
     "source_url": "https://oilprice.com", "category": "rss"},
    {"title": "Qatar shuts down LNG production, LNG shipping rates soar 650%",
     "summary": "Qatar halted all LNG production as conflict escalates. LNG shipping rates soar from $40,000 to $300,000/day. At least one month to restore production. Iran war upends global LNG market, mirroring 2022 crisis.",
     "source_url": "https://thecradle.co", "category": "rss"},
    {"title": "Hezbollah attacks Israel, Israel invades Lebanon",
     "summary": "Hezbollah launched attacks in retaliation for Khamenei killing. Israel authorized ground invasion of Lebanon March 3, ordered displacement of 200,000 below Litani River. Mass displacement in south Lebanon.",
     "source_url": "https://aljazeera.com", "category": "rss"},
    {"title": "War widens: Iran drones hit Azerbaijan, missiles target Qatar, NATO intercepts missile over Turkey",
     "summary": "Iran denies drone attack on Azerbaijan Nakhchivan airport. Iranian missiles target Qatar. NATO intercepts missile over Syria-Turkey border. Conflict spreading beyond original US-Iran theater to neighbors.",
     "source_url": "https://aljazeera.com", "category": "rss"},
    {"title": "US arms Kurdish groups for ground ops in Iran, Tehran threatens Iraq",
     "summary": "Trump spoke to 3+ Kurdish groups. CIA arming Kurdish forces for ground operations in Iran. Tehran threatens Iraq's Kurdish leaders with direct strikes if separatists cross border.",
     "source_url": "https://aljazeera.com", "category": "rss"},
    {"title": "Russia and China condemn but withhold military support for Iran",
     "summary": "Moscow and Beijing condemned US-Israeli attacks but stopped short of military support. China satellites provide intelligence as silent shield. Pakistan under pressure between public sentiment and regional ties.",
     "source_url": "https://aljazeera.com", "category": "rss"},
    {"title": "Yemen declares state of war, global energy trade routes reshuffling",
     "summary": "Ansarallah declares state of war, ready for Axis of Resistance coordination. Iraq halts Kurdistan oil exports. Russia diverts tankers to India. Exxon ships US gasoline to Australia first time. Senate rejects curbs on Trump war powers.",
     "source_url": "https://thecradle.co", "category": "rss"},
]


def main():
    print(f"Seed articles: {len(SEED_ARTICLES)}")

    client_kwargs = {"api_key": API_KEY}
    if BASE_URL:
        client_kwargs["base_url"] = BASE_URL

    # Step 1: Extract events
    analyzer = EventAnalyzer(api_key=API_KEY, model=MODEL, proxy=PROXY)
    analyzer.client = anthropic.Anthropic(**client_kwargs)

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
    dag_engine = DAGEngine(api_key=API_KEY, model=MODEL, proxy=PROXY)
    dag_engine.client = anthropic.Anthropic(**client_kwargs)

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
