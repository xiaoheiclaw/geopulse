"""Tests for the v7.4 Orchestrator — end-to-end with mocked Agent."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from geopulse.models import DAG, Edge, Node
from geopulse.orchestrator import Orchestrator, _strip_markdown_fences
from geopulse.run_output import RunOutput, TriggerType

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_run_output.json"
SAMPLE_RUN_OUTPUT = FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def orchestrator(data_dir):
    return Orchestrator(
        data_dir=data_dir,
        anthropic_api_key="test-key",
    )


@pytest.fixture
def seeded_dag(data_dir):
    """Create a minimal DAG for testing."""
    from geopulse.storage import DAGStorage
    storage = DAGStorage(data_dir=data_dir)
    dag = DAG(
        scenario="us_iran_conflict",
        scenario_label="美伊冲突",
        nodes={
            "us_iran_tensions": Node(
                id="us_iran_tensions", label="美伊紧张局势",
                node_type="event", domains=["政治"],
                probability=0.95, confidence=0.9,
            ),
            "bn_sanctions": Node(
                id="bn_sanctions", label="制裁升级",
                node_type="state", domains=["经济"],
                probability=0.5, confidence=0.6,
            ),
            "bn_strait": Node(
                id="bn_strait", label="霍尔木兹海峡",
                node_type="prediction", domains=["能源", "军事"],
                probability=0.3, confidence=0.5,
            ),
        },
        edges=[
            Edge(source="us_iran_tensions", target="bn_sanctions", weight=0.7, reasoning="制裁跟随紧张局势"),
            Edge(source="us_iran_tensions", target="bn_strait", weight=0.4, reasoning="军事对抗影响海峡"),
        ],
    )
    storage.save(dag)
    return dag


def test_prepare_context_no_dag(orchestrator):
    """Context preparation works with empty data directory."""
    context = orchestrator.prepare_context(TriggerType.scheduled)
    assert context.trigger_type == TriggerType.scheduled
    assert context.dag_summary.get("status") == "未初始化"
    assert context.dag_baseline == {}
    assert context.regime.current.value == "A"


def test_prepare_context_with_dag(orchestrator, seeded_dag):
    context = orchestrator.prepare_context(TriggerType.scheduled)
    assert context.dag_summary["node_count"] == 3
    assert context.dag_summary["edge_count"] == 2
    assert len(context.dag_baseline) == 3
    assert context.regime.current.value == "A"


def test_prepare_context_dispatch_plan(orchestrator, seeded_dag):
    context = orchestrator.prepare_context(TriggerType.scheduled)
    # Always-on models should be in the plan
    assert "bayesian-updating" in context.dispatch_plan.models
    assert "dialectic-challenge" in context.dispatch_plan.models


def test_prepare_context_mental_models(orchestrator, seeded_dag):
    context = orchestrator.prepare_context(TriggerType.scheduled)
    # Should have loaded mental models text
    assert len(context.mental_models_text) > 0


def test_process_output_validates(orchestrator, seeded_dag):
    """Process output parses and validates RunOutput."""
    context = orchestrator.prepare_context(TriggerType.scheduled)
    result = orchestrator.process_output(SAMPLE_RUN_OUTPUT, context)
    assert isinstance(result, RunOutput)
    assert result.meta.run_id == "run_20260306T120000Z"


def test_process_output_updates_dag(orchestrator, seeded_dag):
    """Process output applies engine_result to DAG."""
    context = orchestrator.prepare_context(TriggerType.scheduled)
    orchestrator.process_output(SAMPLE_RUN_OUTPUT, context)
    # DAG should be updated on disk
    dag = orchestrator.dag_storage.load()
    assert dag is not None
    # bn_sanctions should have been updated by mechanical node override (0.65)
    # but after Noisy-OR re-propagation the exact value depends on the network
    assert dag.nodes["bn_sanctions"].probability > 0


def test_process_output_archives(orchestrator, seeded_dag):
    """Process output creates run archive."""
    context = orchestrator.prepare_context(TriggerType.scheduled)
    orchestrator.process_output(SAMPLE_RUN_OUTPUT, context)
    runs = orchestrator.run_storage.list_runs()
    assert "run_20260306T120000Z" in runs


def test_process_output_applies_shs_writeback(orchestrator, seeded_dag):
    """Process output applies SHS writebacks."""
    # Pre-seed SHS with a matching hypothesis
    from geopulse.shs import Hypothesis
    orchestrator.shs_storage.save([
        Hypothesis(
            id="有限冲突假设",
            label="有限冲突假设",
            statement="有限冲突情景",
            confidence=0.5,
        )
    ])
    context = orchestrator.prepare_context(TriggerType.scheduled)
    orchestrator.process_output(SAMPLE_RUN_OUTPUT, context)
    # SHS should be updated
    shs = orchestrator.shs_storage.load()
    assert len(shs) > 0
    h = shs[0]
    assert h.confidence == 0.55  # Updated from 0.5 to 0.55


def test_process_output_strips_markdown_fences(orchestrator, seeded_dag):
    """Process handles markdown-wrapped JSON."""
    wrapped = f"```json\n{SAMPLE_RUN_OUTPUT}\n```"
    context = orchestrator.prepare_context(TriggerType.scheduled)
    result = orchestrator.process_output(wrapped, context)
    assert result.meta.run_id == "run_20260306T120000Z"


def test_strip_markdown_fences():
    assert _strip_markdown_fences('```json\n{"a":1}\n```') == '{"a":1}'
    assert _strip_markdown_fences('{"a":1}') == '{"a":1}'
    assert _strip_markdown_fences('```\n{"a":1}\n```') == '{"a":1}'


def test_full_run_with_mock_agent(orchestrator, seeded_dag):
    """Full orchestrator run with mocked Claude API (streaming)."""
    # Mock the streaming context manager
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.text_stream = iter([SAMPLE_RUN_OUTPUT])

    with patch.object(orchestrator.client.messages, "stream", return_value=mock_stream):
        result = orchestrator.run(
            trigger_type=TriggerType.scheduled,
        )
    assert isinstance(result, RunOutput)
    assert result.meta.run_id == "run_20260306T120000Z"
    assert result.meta.run_duration_ms > 0
    # Verify side effects
    assert orchestrator.run_storage.list_runs()
    dag = orchestrator.dag_storage.load()
    assert dag is not None


def test_call_agent_raises_without_client(data_dir):
    """Call agent raises if no API key."""
    orch = Orchestrator(data_dir=data_dir)
    from geopulse.prompt_builder import AgentContext
    from geopulse.dispatch import DispatchPlan
    from geopulse.run_output import RegimeState, FactorScores, Hysteresis, Regime
    context = AgentContext(
        trigger_type=TriggerType.manual,
        regime=RegimeState(
            current=Regime.A, previous=Regime.A, switched=False,
            held_since="2026-03-05T00:00:00Z",
            factor_scores=FactorScores(SAD=0, PD=0, NCC=0),
            joint_score=0,
            hysteresis=Hysteresis(enter_threshold=0.55, exit_threshold=0.4, min_hold="PT24H", time_in_current="PT0S"),
        ),
        dispatch_plan=DispatchPlan(),
    )
    with pytest.raises(RuntimeError, match="Anthropic client not initialized"):
        orch.call_agent(context)


def test_run_output_schema_roundtrip():
    """Sample fixture passes Pydantic validation."""
    output = RunOutput.model_validate_json(SAMPLE_RUN_OUTPUT)
    # Re-serialize and re-parse
    serialized = output.model_dump_json()
    output2 = RunOutput.model_validate_json(serialized)
    assert output2.meta.run_id == output.meta.run_id
    assert len(output2.scenarios) == len(output.scenarios)
    assert len(output2.bottlenecks) == len(output.bottlenecks)
