"""Model Registry — mental model cards with dynamic credit scoring.

Registry 宪法三条推论:
1. 模型不生成判断，模型只生成视角
2. 判断由 Pipeline 生成
3. Pipeline 是唯一的调用发起方，模型永远不自触发
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .run_output import ModelCost, ModelRole, ModelTrace


class ModelCard(BaseModel):
    """A registered mental model with metadata and credit score."""

    id: str
    name: str
    category: str  # "博弈论" | "认知纪律" | "传导分析" etc.
    layers: list[str]  # Applicable layers ["L2a", "L3.5"]
    role: ModelRole
    cost: ModelCost
    callable_when: str  # Invocation condition description
    scope: str  # Applicable domain + boundaries
    input_spec: str = ""
    output_spec: str = ""
    credit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    always_on: bool = False


class CreditUpdate(BaseModel):
    """Record of a credit score change."""

    model_id: str
    run_id: str
    timestamp: datetime
    old_score: float
    new_score: float
    reason: str


# ── Default model definitions (from Terminal.jsx / runtime_protocol.md) ──

_DEFAULT_MODELS: list[dict] = [
    {
        "id": "bayesian-updating",
        "name": "Bayesian Updating",
        "category": "传导分析",
        "layers": ["L1", "L3"],
        "role": "P",
        "cost": "light",
        "callable_when": "每轮默认加载",
        "scope": "Regime A 基础计算范式。概率更新、先验-后验转化。",
        "input_spec": "prior probabilities + new evidence",
        "output_spec": "posterior probabilities with confidence intervals",
        "always_on": True,
    },
    {
        "id": "dialectic-challenge",
        "name": "辩证质疑",
        "category": "认知纪律",
        "layers": ["L2a", "L3.5"],
        "role": "D",
        "cost": "light",
        "callable_when": "每轮默认加载",
        "scope": "每条分支必须有反论。通用，不限领域。",
        "input_spec": "scenario branch with premises",
        "output_spec": "antithesis + strongest counter-argument",
        "always_on": True,
    },
    {
        "id": "nth-order-reasoning",
        "name": "N阶推演",
        "category": "传导分析",
        "layers": ["L3", "L3.5"],
        "role": "P",
        "cost": "light",
        "callable_when": "每轮默认加载",
        "scope": "传导链展开的基本工具。4阶因果推演。",
        "input_spec": "trigger event + causal DAG context",
        "output_spec": "ordered impact chain with probability decay",
        "always_on": True,
    },
    {
        "id": "schelling-focal",
        "name": "Schelling Focal Point",
        "category": "博弈论",
        "layers": ["L2a", "L3.5", "L4"],
        "role": "P",
        "cost": "medium",
        "callable_when": "存在 S/H 类节点或 Regime B 时",
        "scope": "识别博弈焦点、协调均衡。适用于多方决策场景。不适用于纯传导。",
        "input_spec": "strategic nodes + actor set",
        "output_spec": "focal equilibria candidates with salience scores",
    },
    {
        "id": "schelling-commitment",
        "name": "Schelling Commitment",
        "category": "博弈论",
        "layers": ["L3.5", "L2b"],
        "role": "P",
        "cost": "medium",
        "callable_when": "存在 S/H 类节点或涉及承诺/威慑",
        "scope": "承诺可信度分析、退出成本。适用于威慑与承诺博弈。",
        "input_spec": "actor commitments + exit costs",
        "output_spec": "commitment credibility score + exit cost ratio",
    },
    {
        "id": "carlota-perez",
        "name": "Carlota Perez",
        "category": "传导分析",
        "layers": ["L2a"],
        "role": "P",
        "cost": "light",
        "callable_when": "scenario 涉及技术范式转换或长周期结构变化",
        "scope": "技术革命-金融资本周期。不适用于短期军事冲突。",
        "input_spec": "technology/paradigm shift evidence",
        "output_spec": "cycle phase assessment + structural implications",
    },
    {
        "id": "fearon-audience-cost",
        "name": "Fearon Audience Cost",
        "category": "博弈论",
        "layers": ["L3.5", "L2b"],
        "role": "P",
        "cost": "heavy",
        "callable_when": "关键路径 path_importance > 0.6 或 Regime B",
        "scope": "国内观众成本约束领导人决策。适用于民主/威权政体的对外决策。",
        "input_spec": "leader + domestic political context + public statements",
        "output_spec": "audience cost estimate + escalation/de-escalation probability shift",
    },
    {
        "id": "taleb-antifragile",
        "name": "Taleb 反脆弱",
        "category": "认知纪律",
        "layers": ["L2a", "L5"],
        "role": "D",
        "cost": "medium",
        "callable_when": "执行计划涉及尾部风险或非线性影响",
        "scope": "尾部风险识别、凸性/凹性分析。挑战线性外推假设。",
        "input_spec": "execution plan + position sizing",
        "output_spec": "fragility assessment + tail risk flags",
    },
    {
        "id": "pre-mortem",
        "name": "Pre-Mortem",
        "category": "认知纪律",
        "layers": ["L2a", "L4"],
        "role": "D",
        "cost": "light",
        "callable_when": "任何 scenario.weight > 0.75（高置信度必须质疑）",
        "scope": "假设失败后反推原因。通用纪律模型。",
        "input_spec": "high-confidence scenario + premises",
        "output_spec": "failure modes + overlooked risks",
    },
    {
        "id": "theory-of-constraints",
        "name": "Theory of Constraints",
        "category": "传导分析",
        "layers": ["L2b", "L3"],
        "role": "P",
        "cost": "light",
        "callable_when": "scenario 涉及供应链/产能瓶颈",
        "scope": "识别系统瓶颈、约束链。适用于供应链和产能分析。",
        "input_spec": "supply chain / capacity nodes",
        "output_spec": "bottleneck identification + constraint relaxation paths",
    },
]


class Registry:
    """Model Registry with credit scoring.

    Manages the 10 mental models, provides candidate selection per layer,
    and updates credit scores based on run outcomes.
    """

    def __init__(self, registry_path: Path | str):
        self.registry_path = Path(registry_path)
        self._models: dict[str, ModelCard] = {}

    def load(self) -> dict[str, ModelCard]:
        """Load from disk, or initialize from defaults if not found."""
        if self.registry_path.exists():
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self._models = {
                m["id"]: ModelCard.model_validate(m) for m in raw
            }
        else:
            self._init_defaults()
        return self._models

    def save(self) -> None:
        """Persist current registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = [m.model_dump(mode="json") for m in self._models.values()]
        self.registry_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_candidates(
        self,
        layer: str,
        node_type: str | None = None,
        regime: str | None = None,
    ) -> list[ModelCard]:
        """Return models applicable to a given layer, node type, and regime.

        Implements dispatch rules B.2-B.4:
        - Always-on models are always returned
        - S/H nodes trigger game-theory models (B.3a)
        - Regime B upgrades game-theory priority (B.3b)
        """
        candidates: list[ModelCard] = []
        for m in self._models.values():
            if layer not in m.layers:
                continue
            # Always-on models pass unconditionally
            if m.always_on:
                candidates.append(m)
                continue
            # Game theory models: need S/H node or Regime B
            if m.category == "博弈论":
                if node_type in ("S", "H") or regime == "B":
                    candidates.append(m)
                continue
            # Other conditional models
            candidates.append(m)
        return candidates

    def default_models(self) -> list[ModelCard]:
        """Return the always-on model set (≤ 3)."""
        return [m for m in self._models.values() if m.always_on]

    def update_credits(self, model_trace: ModelTrace, run_id: str) -> list[CreditUpdate]:
        """Update credit scores based on model trace from a completed run.

        P-class: correct_direction → +0.05, wrong → -0.08
        D-class: flagged_risk_materialized → +0.1, missed → -0.03, not_happened → 0
        D-class never degrades below 0.3.
        """
        updates: list[CreditUpdate] = []
        now = datetime.now(timezone.utc)

        for call in model_trace.models_loaded:
            model = self._models.get(call.model_id)
            if not model:
                continue

            old_score = model.credit_score
            # Default: small positive credit for participation
            delta = 0.02
            reason = "participated in run"

            if call.output_summary:
                summary_lower = call.output_summary.lower()
                if "correct" in summary_lower or "confirmed" in summary_lower:
                    delta = 0.05 if model.role == ModelRole.P else 0.10
                    reason = "output confirmed by evidence"
                elif "wrong" in summary_lower or "missed" in summary_lower:
                    delta = -0.08 if model.role == ModelRole.P else -0.03
                    reason = "output contradicted by evidence"

            new_score = max(0.0, min(1.0, old_score + delta))
            # D-class floor: never below 0.3
            if model.role == ModelRole.D:
                new_score = max(0.3, new_score)

            if new_score != old_score:
                model.credit_score = round(new_score, 3)
                updates.append(
                    CreditUpdate(
                        model_id=model.id,
                        run_id=run_id,
                        timestamp=now,
                        old_score=old_score,
                        new_score=model.credit_score,
                        reason=reason,
                    )
                )

        self.save()
        return updates

    def _init_defaults(self) -> None:
        """Initialize registry from hardcoded model definitions."""
        self._models = {}
        for m in _DEFAULT_MODELS:
            card = ModelCard(
                id=m["id"],
                name=m["name"],
                category=m["category"],
                layers=m["layers"],
                role=ModelRole(m["role"]),
                cost=ModelCost(m["cost"]),
                callable_when=m["callable_when"],
                scope=m["scope"],
                input_spec=m.get("input_spec", ""),
                output_spec=m.get("output_spec", ""),
                always_on=m.get("always_on", False),
            )
            self._models[card.id] = card
        self.save()
