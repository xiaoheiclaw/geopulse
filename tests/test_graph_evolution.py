"""Tests for Phase 4: Graph Evolution."""

import json
import pytest
from pathlib import Path

from geopulse.graph_evolution import (
    GraphEvolution,
    classify_proposal,
    validate_proposal,
    _would_create_cycle,
)
from geopulse.run_output import (
    ApprovalLevel,
    GraphProposal,
    ImpactAssessment,
    ProposalType,
    ProposalUrgency,
    RunOutput,
    RunMeta,
    RegimeState,
    EngineResult,
    FactorScores,
    Hysteresis,
    Regime,
    TriggerType,
)
from geopulse.models import DAG, Node, Edge


@pytest.fixture
def sample_dag():
    """A small DAG for testing."""
    dag = DAG(scenario="test", scenario_label="test", version=1)
    dag.nodes = {
        "A": Node(id="A", label="Root A", node_type="event", domains=["military"],
                  probability=0.9, confidence=0.8, evidence=[], reasoning="root"),
        "B": Node(id="B", label="Mid B", node_type="state", domains=["energy"],
                  probability=0.7, confidence=0.6, evidence=[], reasoning="mid"),
        "C": Node(id="C", label="Leaf C", node_type="prediction", domains=["finance"],
                  probability=0.5, confidence=0.5, evidence=[], reasoning="leaf"),
    }
    dag.edges = [
        Edge(source="A", target="B", weight=0.8, reasoning="A→B"),
        Edge(source="B", target="C", weight=0.6, reasoning="B→C"),
    ]
    return dag


@pytest.fixture
def minimal_run_output():
    """Minimal RunOutput for testing."""
    return RunOutput(
        meta=RunMeta(
            run_id="test-run-001",
            timestamp="2026-03-06T14:00:00Z",
            trigger_type=TriggerType.manual,
            evidence_count=0,
        ),
        regime=RegimeState(
            current=Regime.A, previous=Regime.A, switched=False,
            held_since="2026-03-06T00:00:00Z",
            factor_scores=FactorScores(SAD=0.5, PD=0.5, NCC=0.5),
            joint_score=0.5,
            hysteresis=Hysteresis(
                enter_threshold=0.65, exit_threshold=0.40,
                min_hold="72h", time_in_current="24h"
            ),
        ),
        engine_result=EngineResult(regime_used=Regime.A),
        model_trace={"models_loaded": [
            {"model_id": "test-d", "layer": "L2a", "role": "D",
             "called_by": "test", "output_summary": "ok", "cost": "light"},
        ], "total_model_calls": 1},
        graph_proposals=[],
    )


# ── Classification tests ──

def test_classify_l1_leaf_add(sample_dag):
    p = GraphProposal(
        proposal_id="GP-001", type=ProposalType.add_node, target="D",
        payload={"node_id": "D", "type": "M", "parents": ["C"]},
        impact_assessment=ImpactAssessment(
            affected_nodes=["C"], regime_impact=False, scenario_impact=[]
        ),
    )
    assert classify_proposal(p, sample_dag) == ApprovalLevel.L1_AUTO


def test_classify_l2_s_node(sample_dag):
    p = GraphProposal(
        proposal_id="GP-002", type=ProposalType.add_node, target="D",
        payload={"node_id": "D", "type": "S", "parents": ["B"]},
        impact_assessment=ImpactAssessment(
            affected_nodes=["B"], regime_impact=False, scenario_impact=["S1"]
        ),
    )
    level = classify_proposal(p, sample_dag)
    assert level == ApprovalLevel.L2_DEFERRED


def test_classify_l3_delete(sample_dag):
    p = GraphProposal(
        proposal_id="GP-003", type=ProposalType.remove_node, target="B",
        impact_assessment=ImpactAssessment(regime_impact=False),
    )
    assert classify_proposal(p, sample_dag) == ApprovalLevel.L3_HUMAN


def test_classify_l3_regime_impact(sample_dag):
    p = GraphProposal(
        proposal_id="GP-004", type=ProposalType.add_node, target="D",
        payload={"node_id": "D", "type": "M"},
        impact_assessment=ImpactAssessment(regime_impact=True),
    )
    assert classify_proposal(p, sample_dag) == ApprovalLevel.L3_HUMAN


# ── Validation tests ──

def test_validate_add_existing_node(sample_dag):
    p = GraphProposal(
        proposal_id="GP-005", type=ProposalType.add_node, target="A",
        payload={"node_id": "A"},
    )
    errors = validate_proposal(p, sample_dag)
    assert len(errors) == 1
    assert "already exists" in errors[0].reason


def test_validate_add_edge_cycle(sample_dag):
    p = GraphProposal(
        proposal_id="GP-006", type=ProposalType.add_edge, target="edge",
        payload={"source": "C", "target": "A"},
    )
    errors = validate_proposal(p, sample_dag)
    assert len(errors) == 1
    assert "cycle" in errors[0].reason


def test_validate_add_edge_no_cycle(sample_dag):
    p = GraphProposal(
        proposal_id="GP-007", type=ProposalType.add_edge, target="edge",
        payload={"source": "A", "target": "C", "weight": 0.3},
    )
    errors = validate_proposal(p, sample_dag)
    assert len(errors) == 0


def test_validate_remove_midpath_node(sample_dag):
    p = GraphProposal(
        proposal_id="GP-008", type=ProposalType.remove_node, target="B",
    )
    errors = validate_proposal(p, sample_dag)
    assert len(errors) == 1
    assert "causal path" in errors[0].reason


def test_validate_remove_leaf_ok(sample_dag):
    p = GraphProposal(
        proposal_id="GP-009", type=ProposalType.remove_node, target="C",
    )
    errors = validate_proposal(p, sample_dag)
    assert len(errors) == 0  # C is a leaf, only incoming edges


# ── Cycle detection ──

def test_would_create_cycle(sample_dag):
    assert _would_create_cycle(sample_dag, "A", "C") is False  # A→C no back path
    assert _would_create_cycle(sample_dag, "C", "A") is True   # C→A creates cycle


# ── Integration: GraphEvolution ──

def test_graph_evolution_l1_auto_apply(tmp_path, sample_dag, minimal_run_output):
    # Setup
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "dag.json").write_text(json.dumps(sample_dag.model_dump(mode="json"), ensure_ascii=False))

    # Add a L1 proposal
    minimal_run_output.graph_proposals = [
        GraphProposal(
            proposal_id="GP-100", type=ProposalType.add_node, target="D",
            payload={"node_id": "D", "label": "New Leaf", "type": "M",
                     "domains": ["finance"], "parents": ["C"]},
            impact_assessment=ImpactAssessment(
                affected_nodes=["C"], regime_impact=False, scenario_impact=[]
            ),
        ),
    ]

    evo = GraphEvolution(data_dir=data_dir)
    result = evo.process_proposals(minimal_run_output, auto_apply_l1=True)

    assert result["applied"] == 1
    assert result["pending"] == 0

    # Verify DAG was updated
    new_dag = json.loads((data_dir / "dag.json").read_text())
    assert "D" in new_dag["nodes"]
    assert new_dag["version"] == 2  # incremented


def test_graph_evolution_l3_queued(tmp_path, sample_dag, minimal_run_output):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "dag.json").write_text(json.dumps(sample_dag.model_dump(mode="json"), ensure_ascii=False))

    # L3: delete
    minimal_run_output.graph_proposals = [
        GraphProposal(
            proposal_id="GP-200", type=ProposalType.remove_node, target="C",
            justification="No longer relevant",
            impact_assessment=ImpactAssessment(regime_impact=False),
        ),
    ]

    evo = GraphEvolution(data_dir=data_dir)
    result = evo.process_proposals(minimal_run_output, auto_apply_l1=True)

    assert result["applied"] == 0
    assert result["pending"] == 1

    # Check pending queue
    pending = evo.review_pending()
    assert len(pending) == 1
    assert pending[0]["proposal_id"] == "GP-200"


def test_graph_evolution_rejected_on_validation(tmp_path, sample_dag, minimal_run_output):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "dag.json").write_text(json.dumps(sample_dag.model_dump(mode="json"), ensure_ascii=False))

    # Try to add existing node
    minimal_run_output.graph_proposals = [
        GraphProposal(
            proposal_id="GP-300", type=ProposalType.add_node, target="A",
            payload={"node_id": "A", "type": "M"},
            impact_assessment=ImpactAssessment(),
        ),
    ]

    evo = GraphEvolution(data_dir=data_dir)
    result = evo.process_proposals(minimal_run_output)

    assert result["rejected"] == 1
    assert "already exists" in result["errors"][0]
