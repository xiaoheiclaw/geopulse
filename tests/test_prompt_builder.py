"""Tests for Prompt Builder — Agent prompt construction."""
import json

import pytest

from geopulse.dispatch import DispatchPlan
from geopulse.evidence import Evidence
from geopulse.prompt_builder import AgentContext, PromptBuilder
from geopulse.registry import ModelCard
from geopulse.run_output import (
    FactorScores,
    Hysteresis,
    ModelCost,
    ModelRole,
    Regime,
    RegimeState,
    RunOutput,
    TriggerType,
)
from geopulse.shs import Hypothesis


@pytest.fixture
def builder():
    return PromptBuilder()


@pytest.fixture
def regime_state():
    return RegimeState(
        current=Regime.A,
        previous=Regime.A,
        switched=False,
        held_since="2026-03-05T00:00:00Z",
        factor_scores=FactorScores(SAD=0.2, PD=0.3, NCC=0.1),
        joint_score=0.21,
        hysteresis=Hysteresis(
            enter_threshold=0.55, exit_threshold=0.40,
            min_hold="PT24H", time_in_current="PT36H",
        ),
    )


@pytest.fixture
def context(regime_state):
    return AgentContext(
        trigger_type=TriggerType.scheduled,
        evidence=[
            Evidence(id="ev_1", text="Iran tests missile", domains=["军事"]),
        ],
        dag_summary={"node_count": 50, "edge_count": 80},
        dag_baseline={"node_1": 0.65, "node_2": 0.3},
        shs=[
            Hypothesis(
                id="h1", label="有限冲突",
                statement="冲突保持有限规模",
                confidence=0.6, horizon="W1_5",
            ),
        ],
        regime=regime_state,
        dispatch_plan=DispatchPlan(models=["bayesian-updating", "dialectic-challenge"], budget_used=2, budget_limit=20),
        model_cards=[
            ModelCard(
                id="bayesian-updating", name="Bayesian Updating",
                category="传导分析", layers=["L1", "L3"],
                role=ModelRole.P, cost=ModelCost.light,
                callable_when="每轮默认加载", scope="概率更新",
            ),
        ],
        mental_models_text="### 威慑理论\n分析框架...",
    )


def test_system_prompt_contains_constitution(builder):
    prompt = builder.build_system_prompt()
    assert "Registry 宪法" in prompt
    assert "模型不生成判断" in prompt
    assert "RunOutput" in prompt


def test_system_prompt_contains_schema(builder):
    prompt = builder.build_system_prompt()
    assert "RunOutput JSON Schema" in prompt
    assert '"properties"' in prompt


def test_user_prompt_contains_trigger(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "scheduled" in prompt


def test_user_prompt_contains_evidence(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "Iran tests missile" in prompt
    assert "1 条" in prompt


def test_user_prompt_contains_shs(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "有限冲突" in prompt
    assert "Standing Hypothesis Set" in prompt


def test_user_prompt_contains_dag_summary(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "node_count" in prompt
    assert "50" in prompt


def test_user_prompt_contains_baseline(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "L3 基线概率" in prompt
    assert "0.65" in prompt


def test_user_prompt_contains_regime(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "Regime: A" in prompt
    assert "SAD=" in prompt


def test_user_prompt_contains_models(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "Bayesian Updating" in prompt
    assert "bayesian-updating" in prompt


def test_user_prompt_contains_mental_models(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "威慑理论" in prompt


def test_user_prompt_contains_instruction(builder, context):
    prompt = builder.build_user_prompt(context)
    assert "L1→L2a→L2b→L3.5→L4→L5" in prompt
    assert "RunOutput JSON" in prompt


def test_user_prompt_no_evidence(builder, regime_state):
    context = AgentContext(
        trigger_type=TriggerType.manual,
        regime=regime_state,
        dispatch_plan=DispatchPlan(),
    )
    prompt = builder.build_user_prompt(context)
    assert "无新证据" in prompt


def test_user_prompt_previous_run(builder, context):
    context.previous_run_summary = "Run run_001: 3 scenarios"
    prompt = builder.build_user_prompt(context)
    assert "上轮 RunOutput" in prompt
    assert "run_001" in prompt


def test_schema_instruction_valid_json(builder):
    instruction = builder.build_run_output_schema_instruction()
    # Extract JSON from the instruction
    json_start = instruction.index("{")
    json_end = instruction.rindex("}") + 1
    schema = json.loads(instruction[json_start:json_end])
    assert "properties" in schema
    assert "meta" in schema["properties"]
