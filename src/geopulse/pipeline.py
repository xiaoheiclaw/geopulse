"""Pipeline orchestration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analyzer import EventAnalyzer
from .dag_engine import DAGEngine
from .ingester import ReadwiseIngester
from .models import DAG, Event
from .propagator import propagate
from .red_team import audit_dag
from .reporter import Reporter
from .storage import DAGStorage

DEFAULT_SCENARIO = "us_iran_conflict"
DEFAULT_SCENARIO_LABEL = "美伊冲突"


class Pipeline:
    """Orchestrates the full GeoPulse workflow: ingest -> analyze -> update -> report."""

    def __init__(
        self,
        readwise_token: str,
        anthropic_api_key: str,
        data_dir: Path | str = "data",
        proxy: str | None = "http://127.0.0.1:7890",
        readwise_tag: str = "geopulse",
        llm_model: str = "claude-sonnet-4-6",
        base_url: str | None = None,
    ):
        self.ingester = ReadwiseIngester(
            token=readwise_token, tag=readwise_tag, proxy=proxy
        )
        self.analyzer = EventAnalyzer(
            api_key=anthropic_api_key, model=llm_model, proxy=proxy, base_url=base_url
        )
        self.dag_engine = DAGEngine(
            api_key=anthropic_api_key, model=llm_model, proxy=proxy, base_url=base_url
        )
        self.storage = DAGStorage(data_dir=data_dir)
        self.reporter = Reporter()
        self.events_log = Path(data_dir) / "events.jsonl"

    def run(self) -> str | None:
        """Execute the full pipeline. Returns a report string or None if no events."""
        articles = self.ingester.fetch()
        if not articles:
            return None

        all_events: list[Event] = []
        for article in articles:
            events = self.analyzer.analyze(article)
            all_events.extend(events)

        if not all_events:
            return None

        self._log_events(all_events)

        old_dag = self.storage.load()
        if old_dag is None:
            old_dag = DAG(
                scenario=DEFAULT_SCENARIO, scenario_label=DEFAULT_SCENARIO_LABEL
            )

        updated_dag = self.dag_engine.update(old_dag, all_events)
        propagated_dag = propagate(updated_dag)

        # Red Team audit
        audit_report = audit_dag(propagated_dag, old_dag=old_dag if old_dag.nodes else None)
        print(audit_report.summary())

        self.storage.save(propagated_dag)

        analysis = getattr(updated_dag, "_analysis", "")
        insights = getattr(updated_dag, "_model_insights", [])
        events_summary = [e.headline for e in all_events[:10]]

        report = self.reporter.daily_report(
            propagated_dag,
            events_summary=events_summary,
            old_dag=old_dag if old_dag.nodes else None,
            analysis=analysis,
            model_insights=insights,
        )
        return report

    def _extract_overrides(self, update_json: dict[str, Any]) -> dict[str, float]:
        """Extract LLM explicit probability overrides from update JSON."""
        overrides: dict[str, float] = {}
        for ch in update_json.get("updates", update_json).get("probability_changes", []):
            nid = ch.get("node_id", "")
            if nid and "new_probability" in ch:
                overrides[nid] = ch["new_probability"]
        return overrides

    def apply_external_update(self, update_json: dict[str, Any]) -> str:
        """Apply an externally generated LLM update (from Agent) to the DAG."""
        old_dag = self.storage.load()
        if old_dag is None:
            old_dag = DAG(
                scenario=DEFAULT_SCENARIO, scenario_label=DEFAULT_SCENARIO_LABEL
            )

        updated_dag = self.dag_engine._apply_updates(old_dag, update_json)
        overrides = self._extract_overrides(update_json)
        propagated_dag = propagate(updated_dag, overrides=overrides)

        # Red Team audit
        audit_report = audit_dag(propagated_dag, old_dag=old_dag if old_dag.nodes else None)
        print(audit_report.summary())

        self.storage.save(propagated_dag)

        analysis = getattr(updated_dag, "_analysis", "")
        insights = getattr(updated_dag, "_model_insights", [])
        
        # For external updates, we might not have the original events list
        # but the update_json usually contains some reasoning/evidence
        events_summary = ["外部 Agent 分析更新"]

        report = self.reporter.daily_report(
            propagated_dag,
            events_summary=events_summary,
            old_dag=old_dag if old_dag.nodes else None,
            analysis=analysis,
            model_insights=insights,
        )
        return report

    def _log_events(self, events: list[Event]) -> None:
        """Append events to the JSONL log file."""
        self.events_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_log, "a", encoding="utf-8") as f:
            for event in events:
                entry = event.model_dump(mode="json")
                entry["logged_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def apply_external_analysis(self, analysis_data: dict[str, Any]) -> str | None:
        """Apply pre-computed analysis (from Agent) to the DAG and generate report."""
        old_dag = self.storage.load()
        if old_dag is None:
            old_dag = DAG(
                scenario=DEFAULT_SCENARIO, scenario_label=DEFAULT_SCENARIO_LABEL
            )

        # analysis_data should follow the same structure as DAGEngine._call_llm output
        updated_dag = self.dag_engine._apply_updates(old_dag, analysis_data)
        overrides = self._extract_overrides(analysis_data)
        propagated_dag = propagate(updated_dag, overrides=overrides)

        # Red Team audit
        audit_report = audit_dag(propagated_dag, old_dag=old_dag if old_dag.nodes else None)
        print(audit_report.summary())

        self.storage.save(propagated_dag)

        # Generate report
        analysis = analysis_data.get("analysis", "")
        insights = analysis_data.get("model_insights", [])
        
        # Reconstruct events for the report if provided
        events_raw = analysis_data.get("events", [])
        all_events = []
        for ev in events_raw:
            all_events.append(Event(**ev))
        
        if all_events:
            self._log_events(all_events)

        events_summary = [e.headline for e in all_events[:10]]

        report = self.reporter.daily_report(
            propagated_dag,
            events_summary=events_summary,
            old_dag=old_dag if old_dag.nodes else None,
            analysis=analysis,
            model_insights=insights,
        )
        return report
