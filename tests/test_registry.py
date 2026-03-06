"""Tests for Model Registry and credit scoring."""
import json

import pytest

from geopulse.registry import ModelCard, Registry, CreditUpdate, _DEFAULT_MODELS
from geopulse.run_output import ModelCall, ModelCost, ModelRole, ModelTrace


@pytest.fixture
def registry_path(tmp_path):
    return tmp_path / "registry.json"


@pytest.fixture
def registry(registry_path):
    r = Registry(registry_path)
    r.load()
    return r


def test_default_models_count(registry):
    assert len(registry._models) == 10


def test_default_models_always_on(registry):
    always_on = registry.default_models()
    assert len(always_on) == 3
    ids = {m.id for m in always_on}
    assert ids == {"bayesian-updating", "dialectic-challenge", "nth-order-reasoning"}


def test_default_models_always_on_are_light(registry):
    for m in registry.default_models():
        assert m.cost == ModelCost.light


def test_load_from_disk(registry, registry_path):
    """After init, registry.json exists on disk and can be reloaded."""
    assert registry_path.exists()
    r2 = Registry(registry_path)
    r2.load()
    assert len(r2._models) == 10


def test_save_and_reload_preserves_credits(registry, registry_path):
    registry._models["bayesian-updating"].credit_score = 0.8
    registry.save()
    r2 = Registry(registry_path)
    r2.load()
    assert r2._models["bayesian-updating"].credit_score == 0.8


def test_get_candidates_layer_filter(registry):
    candidates = registry.get_candidates(layer="L1")
    ids = {c.id for c in candidates}
    assert "bayesian-updating" in ids
    # Schelling focal is L2a/L3.5/L4, not L1
    assert "schelling-focal" not in ids


def test_get_candidates_game_theory_with_sh_node(registry):
    candidates = registry.get_candidates(layer="L3.5", node_type="S")
    ids = {c.id for c in candidates}
    assert "schelling-commitment" in ids
    assert "schelling-focal" in ids


def test_get_candidates_game_theory_regime_b(registry):
    candidates = registry.get_candidates(layer="L3.5", regime="B")
    ids = {c.id for c in candidates}
    assert "schelling-commitment" in ids


def test_get_candidates_no_game_theory_without_trigger(registry):
    """Game theory models not returned for M-type nodes in Regime A."""
    candidates = registry.get_candidates(layer="L3.5", node_type="M", regime="A")
    ids = {c.id for c in candidates}
    # Always-on models that match L3.5 should still be present
    assert "nth-order-reasoning" in ids
    # But non-always-on game theory should not
    assert "schelling-commitment" not in ids


def test_update_credits_positive(registry):
    trace = ModelTrace(
        models_loaded=[
            ModelCall(
                model_id="bayesian-updating",
                layer="L1",
                role=ModelRole.P,
                called_by="test",
                output_summary="output confirmed by evidence",
                cost=ModelCost.light,
            )
        ]
    )
    old = registry._models["bayesian-updating"].credit_score
    updates = registry.update_credits(trace, run_id="run_test")
    assert len(updates) == 1
    assert updates[0].new_score > old


def test_update_credits_d_class_floor(registry):
    """D-class models never go below 0.3."""
    registry._models["dialectic-challenge"].credit_score = 0.31
    trace = ModelTrace(
        models_loaded=[
            ModelCall(
                model_id="dialectic-challenge",
                layer="L2a",
                role=ModelRole.D,
                called_by="test",
                output_summary="missed risk that happened",
                cost=ModelCost.light,
            )
        ]
    )
    updates = registry.update_credits(trace, run_id="run_test")
    model = registry._models["dialectic-challenge"]
    assert model.credit_score >= 0.3


def test_model_card_roles():
    """Check P/D distribution matches spec."""
    p_models = [m for m in _DEFAULT_MODELS if m["role"] == "P"]
    d_models = [m for m in _DEFAULT_MODELS if m["role"] == "D"]
    assert len(p_models) == 7  # Bayesian, N-order, Schelling x2, Carlota, Fearon, ToC
    assert len(d_models) == 3  # 辩证质疑, Taleb, Pre-Mortem


def test_model_ids_unique():
    ids = [m["id"] for m in _DEFAULT_MODELS]
    assert len(ids) == len(set(ids))
