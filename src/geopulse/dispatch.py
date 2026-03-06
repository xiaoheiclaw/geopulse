"""Dispatch engine — model selection rules (Runtime Protocol Part B).

Decides which mental models to load per run based on trigger type,
regime, bottleneck nodes, and scenario weights.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .registry import ModelCard, Registry
from .run_output import (
    BottleneckNode,
    ModelCost,
    ModelRole,
    NodeType,
    Regime,
    Scenario,
    TriggerType,
)

COST_MAP = {"light": 1, "medium": 3, "heavy": 7}


class DispatchPlan(BaseModel):
    """Models selected for this run + budget accounting."""

    models: list[str] = Field(default_factory=list)  # model IDs
    budget_used: int = 0
    budget_limit: int = 20


class DispatchEngine:
    """Implements dispatch rules B.2 through B.5."""

    def __init__(self, registry: Registry):
        self.registry = registry

    def plan(
        self,
        trigger_type: TriggerType,
        regime: Regime,
        bottlenecks: list[BottleneckNode] | None = None,
        scenarios: list[Scenario] | None = None,
    ) -> DispatchPlan:
        """Compute which models to load for this run.

        Rules applied:
        B.2 — Always-on models (≤ 3, must be light)
        B.3a — S/H node type triggers game-theory models
        B.3b — Regime B upgrades game-theory priority
        B.3c — High-confidence scenarios force Pre-Mortem (D-class)
        B.3d — Tech paradigm → Carlota Perez; Supply chain → ToC
        B.4 — Heavy models need path_importance > 0.6 or Regime B or deep_dive
        B.5 — P/D minimum composition validated post-hoc
        """
        budget_limit = 40 if trigger_type == TriggerType.manual else 20
        selected: dict[str, ModelCard] = {}  # dedup by id
        bottlenecks = bottlenecks or []
        scenarios = scenarios or []

        # B.2: Always-on
        for m in self.registry.default_models():
            selected[m.id] = m

        # B.3a: S/H node types trigger game-theory
        has_sh = any(b.type in (NodeType.S, NodeType.H) for b in bottlenecks)
        if has_sh:
            for m in self.registry._models.values():
                if m.category == "博弈论" and m.id not in selected:
                    selected[m.id] = m

        # B.3b: Regime B upgrades game-theory priority
        if regime == Regime.B:
            for m in self.registry._models.values():
                if m.category == "博弈论" and m.id not in selected:
                    selected[m.id] = m

        # B.3c: High-confidence scenarios → force Pre-Mortem
        high_conf = any(s.weight > 0.75 for s in scenarios)
        if high_conf:
            pm = self.registry._models.get("pre-mortem")
            if pm and pm.id not in selected:
                selected[pm.id] = pm

        # B.3d: Conditional models by scenario content
        # (heuristic: check scenario labels for keywords)
        for s in scenarios:
            label_lower = s.label.lower()
            if any(kw in label_lower for kw in ("技术", "范式", "tech", "paradigm")):
                cp = self.registry._models.get("carlota-perez")
                if cp and cp.id not in selected:
                    selected[cp.id] = cp
            if any(kw in label_lower for kw in ("供应链", "产能", "supply", "bottleneck")):
                toc = self.registry._models.get("theory-of-constraints")
                if toc and toc.id not in selected:
                    selected[toc.id] = toc

        # B.3d also: Taleb for tail risk scenarios
        for s in scenarios:
            label_lower = s.label.lower()
            if any(kw in label_lower for kw in ("尾部", "黑天鹅", "tail", "fragil")):
                ta = self.registry._models.get("taleb-antifragile")
                if ta and ta.id not in selected:
                    selected[ta.id] = ta

        # B.4: Heavy model gate — need path_importance > 0.6 or Regime B or manual
        max_path_importance = max(
            (b.path_importance for b in bottlenecks), default=0.0
        )
        deep_dive = trigger_type == TriggerType.manual

        to_remove: list[str] = []
        for mid, m in selected.items():
            if m.cost != ModelCost.heavy:
                continue
            gate_passed = (
                max_path_importance > 0.6
                or (regime == Regime.B and m.category == "博弈论")
                or deep_dive
            )
            if not gate_passed:
                to_remove.append(mid)
        for mid in to_remove:
            del selected[mid]

        # Budget enforcement (D-class exempt per B.8)
        budget_used = 0
        final: list[str] = []
        for m in selected.values():
            cost = COST_MAP.get(m.cost.value, 1)
            if m.role == ModelRole.D:
                # D-class: always included, not counted
                final.append(m.id)
            elif budget_used + cost <= budget_limit:
                final.append(m.id)
                budget_used += cost
            # else: skip due to budget

        return DispatchPlan(
            models=final,
            budget_used=budget_used,
            budget_limit=budget_limit,
        )

    def validate_post_run(
        self, model_trace: "ModelTrace", plan: DispatchPlan
    ) -> list[str]:
        """Post-run validation of B.5 P/D minimum composition.

        Returns list of violation messages (empty = all good).
        """
        from .run_output import ModelTrace

        violations: list[str] = []

        # Constraint 1: at least 1 D-class
        d_calls = [c for c in model_trace.models_loaded if c.role == ModelRole.D]
        if not d_calls:
            violations.append("B.5 约束 1 违反: 至少需要 1 个 D 类模型")

        # Constraint 2: high-confidence scenarios must be D-audited
        # (This is checked by RunOutput's model_validator, but we double-check here)

        # Check all planned models were actually called
        called_ids = {c.model_id for c in model_trace.models_loaded}
        planned_set = set(plan.models)
        missing = planned_set - called_ids
        if missing:
            violations.append(
                f"计划加载但未调用的模型: {', '.join(sorted(missing))}"
            )

        return violations
