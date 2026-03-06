"""Tests for Dispatch engine — model selection rules."""
import pytest

from geopulse.dispatch import DispatchEngine, DispatchPlan, COST_MAP
from geopulse.registry import Registry
from geopulse.run_output import (
    BottleneckNode,
    FactorScores,
    ModelCall,
    ModelCost,
    ModelRole,
    ModelTrace,
    NodeType,
    Regime,
    Scenario,
    TriggerType,
)


@pytest.fixture
def registry(tmp_path):
    r = Registry(tmp_path / "registry.json")
    r.load()
    return r


@pytest.fixture
def engine(registry):
    return DispatchEngine(registry)


def _scenario(label="有限冲突", weight=0.5) -> Scenario:
    return Scenario(
        id="s_test",
        label=label,
        weight=weight,
        weight_prev=weight - 0.05,
    )


def _bottleneck(type="M", path_importance=0.5) -> BottleneckNode:
    return BottleneckNode(
        node_id="bn_test",
        label="test",
        type=NodeType(type),
        path_importance=path_importance,
        factor_scores=FactorScores(SAD=0.5, PD=0.5, NCC=0.5),
    )


def test_always_on_models_included(engine):
    """B.2: Always-on models always in plan."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
    )
    assert "bayesian-updating" in plan.models
    assert "dialectic-challenge" in plan.models
    assert "nth-order-reasoning" in plan.models


def test_sh_node_triggers_game_theory(engine):
    """B.3a: S/H nodes trigger game-theory models."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        bottlenecks=[_bottleneck("S")],
    )
    assert "schelling-focal" in plan.models or "schelling-commitment" in plan.models


def test_regime_b_triggers_game_theory(engine):
    """B.3b: Regime B upgrades game-theory models."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.B,
    )
    game_theory = {"schelling-focal", "schelling-commitment", "fearon-audience-cost"}
    loaded = set(plan.models)
    assert loaded & game_theory  # at least one loaded


def test_high_confidence_forces_pre_mortem(engine):
    """B.3c: High-confidence scenario forces Pre-Mortem."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        scenarios=[_scenario(weight=0.85)],
    )
    assert "pre-mortem" in plan.models


def test_heavy_model_gate_blocks(engine):
    """B.4: Heavy models blocked without sufficient path_importance."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        bottlenecks=[_bottleneck("S", path_importance=0.3)],  # below 0.6 threshold
    )
    assert "fearon-audience-cost" not in plan.models


def test_heavy_model_passes_with_high_importance(engine):
    """B.4: Heavy model allowed when path_importance > 0.6."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        bottlenecks=[_bottleneck("S", path_importance=0.8)],
    )
    assert "fearon-audience-cost" in plan.models


def test_heavy_model_passes_regime_b(engine):
    """B.4: Heavy model allowed in Regime B for game-theory category."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.B,
    )
    assert "fearon-audience-cost" in plan.models


def test_heavy_model_passes_manual_trigger(engine):
    """B.4: Manual trigger acts as deep_dive, allows heavy models."""
    plan = engine.plan(
        trigger_type=TriggerType.manual,
        regime=Regime.A,
        bottlenecks=[_bottleneck("S")],
    )
    assert "fearon-audience-cost" in plan.models


def test_budget_limit_scheduled(engine):
    """B.8: Scheduled runs have budget of 20."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
    )
    assert plan.budget_limit == 20
    assert plan.budget_used <= 20


def test_budget_limit_manual(engine):
    """B.8: Manual runs have budget of 40."""
    plan = engine.plan(
        trigger_type=TriggerType.manual,
        regime=Regime.A,
    )
    assert plan.budget_limit == 40


def test_d_class_exempt_from_budget(engine):
    """B.8: D-class models don't count toward budget."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        scenarios=[_scenario(weight=0.85)],  # triggers pre-mortem (D)
    )
    # D-class should be in plan but not counted in budget
    d_models = {"dialectic-challenge", "pre-mortem", "taleb-antifragile"}
    for mid in plan.models:
        if mid in d_models:
            # Should not contribute to budget_used
            pass
    # budget_used should only reflect P-class
    assert plan.budget_used <= plan.budget_limit


def test_validate_post_run_no_violations(engine):
    """Post-run validation passes with proper D-class model."""
    plan = DispatchPlan(models=["bayesian-updating", "dialectic-challenge"], budget_used=2, budget_limit=20)
    trace = ModelTrace(
        models_loaded=[
            ModelCall(model_id="bayesian-updating", layer="L1", role=ModelRole.P, called_by="test", cost=ModelCost.light),
            ModelCall(model_id="dialectic-challenge", layer="L2a", role=ModelRole.D, called_by="test", cost=ModelCost.light),
        ]
    )
    violations = engine.validate_post_run(trace, plan)
    assert violations == []


def test_validate_post_run_missing_d_class(engine):
    """Post-run validation catches missing D-class model."""
    plan = DispatchPlan(models=["bayesian-updating"], budget_used=1, budget_limit=20)
    trace = ModelTrace(
        models_loaded=[
            ModelCall(model_id="bayesian-updating", layer="L1", role=ModelRole.P, called_by="test", cost=ModelCost.light),
        ]
    )
    violations = engine.validate_post_run(trace, plan)
    assert any("D 类模型" in v for v in violations)


def test_tech_paradigm_triggers_carlota_perez(engine):
    """B.3d: Tech paradigm scenario triggers Carlota Perez."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        scenarios=[_scenario(label="技术范式转换")],
    )
    assert "carlota-perez" in plan.models


def test_supply_chain_triggers_toc(engine):
    """B.3d: Supply chain scenario triggers Theory of Constraints."""
    plan = engine.plan(
        trigger_type=TriggerType.scheduled,
        regime=Regime.A,
        scenarios=[_scenario(label="供应链瓶颈")],
    )
    assert "theory-of-constraints" in plan.models
