"""v7.4 Pipeline Orchestrator — the central coordinator.

Three-phase flow:
1. prepare_context: Code prepares Agent input (evidence, DAG, SHS, regime, dispatch)
2. call_agent: Single Claude API call
3. process_output: Code validates RunOutput, runs L3 Noisy-OR, hybrid recompute,
   SHS writeback, registry credit update, archive

MVP strategy: Single API call for the full pipeline. L3 baseline is pre-computed
and passed in context; Agent outputs L3.5 overrides; code recomputes downstream.
"""
from __future__ import annotations

import json
import logging
import re
import time
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import httpx

from .dispatch import DispatchEngine, DispatchPlan
from .evidence import Evidence, events_to_evidence
from .mental_models import build_prompt_injection
from .models import DAG
from .propagator import propagate
from .prompt_builder import AgentContext, PromptBuilder
from .regime import RegimeDetector
from .registry import Registry
from .run_output import (
    HybridResult,
    Regime,
    RunOutput,
    TriggerType,
)
from .run_storage import RunOutputStorage
from .shs import SHSStorage
from .storage import DAGStorage

logger = logging.getLogger(__name__)


class Orchestrator:
    """v7.4 Pipeline orchestrator."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        anthropic_api_key: str | None = None,
        base_url: str | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 8192,
    ):
        self.data_dir = Path(data_dir)
        self.model = model
        self.max_tokens = max_tokens

        # Sub-systems
        self.dag_storage = DAGStorage(data_dir=self.data_dir)
        self.shs_storage = SHSStorage(data_dir=self.data_dir)
        self.run_storage = RunOutputStorage(data_dir=self.data_dir)
        self.registry = Registry(self.data_dir / "registry.json")
        self.registry.load()
        self.regime_detector = RegimeDetector()
        self.dispatch_engine = DispatchEngine(self.registry)
        self.prompt_builder = PromptBuilder()

        # Anthropic client
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        effective_base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        if effective_base_url:
            kwargs["base_url"] = effective_base_url
        else:
            # Direct API: use HTTP proxy if available (needed in China)
            http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or os.getenv("HTTPS_PROXY")
            if http_proxy:
                kwargs["http_client"] = httpx.Client(proxy=http_proxy)
        # Long timeout for relay/streaming (10 min read, 5 min connect)
        kwargs["timeout"] = httpx.Timeout(600.0, connect=300.0)
        self.client = anthropic.Anthropic(**kwargs) if api_key else None

    def prepare_context(
        self,
        trigger_type: TriggerType,
        trigger_event: str | None = None,
        evidence: list[Evidence] | None = None,
    ) -> AgentContext:
        """Phase 1: Prepare Agent input context.

        1. Load DAG, SHS, previous RunOutput
        2. Use provided evidence or empty list
        3. Run L3 baseline (Noisy-OR pre-compute)
        4. Determine regime (default A for first run)
        5. Plan dispatch (model selection)
        6. Load mental models text
        """
        dag = self.dag_storage.load()
        shs = self.shs_storage.load()
        prev_run = self.run_storage.latest()
        evidence = evidence or []

        # DAG summary
        if dag:
            orders = dag.compute_orders()
            dag_summary = {
                "scenario": dag.scenario_label,
                "version": dag.version,
                "node_count": len(dag.nodes),
                "edge_count": len(dag.edges),
                "max_order": max(orders.values()) if orders else 0,
                "global_risk_index": dag.global_risk_index(),
                "critical_nodes": [
                    {"id": nid, "label": n.label, "prob": n.probability}
                    for nid, n in sorted(
                        dag.nodes.items(),
                        key=lambda x: x[1].probability,
                        reverse=True,
                    )[:10]
                ],
            }
            # L3 baseline
            propagated_dag = propagate(dag)
            dag_baseline = {
                nid: round(n.probability, 4)
                for nid, n in propagated_dag.nodes.items()
            }
        else:
            dag_summary = {"status": "未初始化"}
            dag_baseline = {}

        # Regime (use previous or default)
        if prev_run:
            regime_state = prev_run.regime
        else:
            from .run_output import FactorScores, Hysteresis, RegimeState
            regime_state = self.regime_detector.determine_regime(
                FactorScores(SAD=0.0, PD=0.0, NCC=0.0),
                current=None,
            )

        # Dispatch
        prev_scenarios = prev_run.scenarios if prev_run else []
        prev_bottlenecks = prev_run.bottlenecks if prev_run else []
        dispatch_plan = self.dispatch_engine.plan(
            trigger_type=trigger_type,
            regime=regime_state.current,
            bottlenecks=prev_bottlenecks,
            scenarios=prev_scenarios,
        )

        # Model cards for dispatched models
        model_cards = [
            self.registry._models[mid]
            for mid in dispatch_plan.models
            if mid in self.registry._models
        ]

        # Mental models text
        mental_models_text = build_prompt_injection()

        # Previous run summary
        prev_summary = None
        if prev_run:
            prev_summary = (
                f"Run {prev_run.meta.run_id} @ {prev_run.meta.timestamp.isoformat()}: "
                f"{len(prev_run.scenarios)} scenarios, "
                f"regime={prev_run.regime.current.value}, "
                f"evidence_count={prev_run.meta.evidence_count}"
            )

        return AgentContext(
            trigger_type=trigger_type,
            trigger_event=trigger_event,
            evidence=evidence,
            dag_summary=dag_summary,
            dag_baseline=dag_baseline,
            shs=shs,
            regime=regime_state,
            dispatch_plan=dispatch_plan,
            model_cards=model_cards,
            mental_models_text=mental_models_text,
            previous_run_summary=prev_summary,
        )

    def call_agent(self, context: AgentContext, max_retries: int = 3) -> str:
        """Phase 2: Call Claude API with structured prompt (streaming).

        Uses streaming with retry on relay connection drops.
        Returns raw JSON string from the Agent.
        """
        if not self.client:
            raise RuntimeError("Anthropic client not initialized (missing API key)")

        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(context)

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            chunks: list[str] = []
            try:
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                ) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                    # Check if output was truncated
                    final = stream.get_final_message()
                    if final.stop_reason == "max_tokens":
                        total_chars = sum(len(c) for c in chunks)
                        logger.warning(
                            "Agent output truncated at %d chars (max_tokens=%d). "
                            "Consider increasing max_tokens.",
                            total_chars, self.max_tokens,
                        )
                return "".join(chunks)

            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
                total_chars = sum(len(c) for c in chunks)
                last_error = e
                logger.warning(
                    "Relay connection dropped on attempt %d/%d "
                    "(%d chars received): %s",
                    attempt, max_retries, total_chars, e,
                )
                if attempt < max_retries:
                    wait = attempt * 5  # 5s, 10s backoff
                    logger.info("Retrying in %ds...", wait)
                    time.sleep(wait)

        raise RuntimeError(
            f"Agent call failed after {max_retries} attempts: {last_error}"
        )

    def process_output(
        self, raw_json: str, context: AgentContext
    ) -> RunOutput:
        """Phase 3: Validate + post-process Agent output.

        1. Parse JSON → RunOutput (Pydantic validation)
        2. Extract DAG updates from engine_result
        3. Run L3 Noisy-OR propagation
        4. Apply Hybrid overrides + recompute downstream
        5. Update DAG and save
        6. Apply SHS writebacks
        7. Update Registry credits
        8. Archive RunOutput
        """
        # Strip markdown fences if present
        cleaned = _strip_markdown_fences(raw_json)

        # Parse and validate
        run_output = RunOutput.model_validate_json(cleaned)

        # Load current DAG
        dag = self.dag_storage.load()
        if dag:
            # Build overrides from engine_result
            overrides: dict[str, float] = {}

            # Mechanical nodes: Agent-assessed probabilities
            for mech in run_output.engine_result.mechanical_nodes:
                if mech.node_id in dag.nodes:
                    overrides[mech.node_id] = mech.propagated_prob

            # Strategic nodes: use selected equilibrium probability
            for strat in run_output.engine_result.strategic_nodes:
                if strat.node_id in dag.nodes and strat.equilibria:
                    # Find selected equilibrium
                    for eq in strat.equilibria:
                        if eq.eq_id == strat.selected_eq:
                            overrides[strat.node_id] = eq.probability
                            break

            # Run L3 Noisy-OR with overrides
            propagated_dag = propagate(dag, overrides=overrides)

            # Hybrid nodes: apply L3.5 override + recompute downstream
            hybrid_overrides: dict[str, float] = {}
            for hybrid in run_output.engine_result.hybrid_nodes:
                if hybrid.node_id in propagated_dag.nodes:
                    hybrid_overrides[hybrid.node_id] = hybrid.override_prob

            if hybrid_overrides:
                propagated_dag = propagate(propagated_dag, overrides=hybrid_overrides)

            # Save updated DAG
            self.dag_storage.save(propagated_dag)

        # Regime update from bottlenecks
        if run_output.bottlenecks:
            factors = self.regime_detector.compute_factors(run_output.bottlenecks)
            new_regime = self.regime_detector.determine_regime(
                factors, current=context.regime
            )
            run_output.regime = new_regime

        # SHS writebacks
        if run_output.shs_writeback:
            self.shs_storage.apply_writebacks(
                run_output.shs_writeback,
                run_id=run_output.meta.run_id,
            )

        # Registry credit update
        if run_output.model_trace.models_loaded:
            self.registry.update_credits(
                run_output.model_trace,
                run_id=run_output.meta.run_id,
            )

        # Phase 4: Graph Evolution — process structural proposals
        if run_output.graph_proposals:
            from .graph_evolution import GraphEvolution
            graph_evo = GraphEvolution(data_dir=self.data_dir)
            evo_result = graph_evo.process_proposals(
                run_output, auto_apply_l1=True
            )
            logger.info(
                f"Phase 4: {evo_result['applied']} applied, "
                f"{evo_result['pending']} pending, "
                f"{evo_result['rejected']} rejected"
            )

        # Archive RunOutput
        self.run_storage.save(run_output)

        return run_output

    def run(
        self,
        trigger_type: TriggerType = TriggerType.scheduled,
        trigger_event: str | None = None,
        evidence: list[Evidence] | None = None,
    ) -> RunOutput:
        """Full v7.4 run: prepare → call Agent → process output."""
        start = time.time()

        context = self.prepare_context(trigger_type, trigger_event, evidence)
        raw = self.call_agent(context)
        run_output = self.process_output(raw, context)

        # Update run duration
        duration_ms = int((time.time() - start) * 1000)
        run_output.meta.run_duration_ms = duration_ms

        # Re-save with updated duration
        self.run_storage.save(run_output)

        return run_output


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (possibly with language tag)
        text = re.sub(r"^```\w*\n?", "", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
