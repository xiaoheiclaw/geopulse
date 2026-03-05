"""Tests for DAG engine LLM updates."""
import json
from unittest.mock import MagicMock, patch
import pytest
from geopulse.dag_engine import DAGEngine
from geopulse.models import DAG, Edge, Event, Node


def _sample_dag() -> DAG:
    return DAG(
        scenario="us_iran_conflict", scenario_label="美伊冲突",
        nodes={"us_iran_conflict": Node(
            id="us_iran_conflict", label="美伊军事冲突",
            domains=["军事"], probability=0.35, confidence=0.8,
            evidence=["baseline"], reasoning="root",
        )},
        edges=[],
    )

def _sample_event() -> Event:
    return Event(headline="美军航母进入波斯湾",
                 details="林肯号航母战斗群通过霍尔木兹海峡",
                 entities=["美国", "波斯湾"], domains=["军事"], significance=4)


class TestDAGEngine:
    def test_applies_new_nodes(self):
        engine = DAGEngine(api_key="fake")
        dag = _sample_dag()
        llm_response = {
            "analysis": "航母部署提升冲突概率",
            "model_insights": [],
            "updates": {
                "new_nodes": [{"id": "carrier_deployment", "label": "航母部署波斯湾",
                               "domains": ["军事"], "probability": 0.80, "confidence": 0.9,
                               "evidence": ["林肯号进入波斯湾"], "reasoning": "军事准备"}],
                "new_edges": [{"from": "carrier_deployment", "to": "us_iran_conflict",
                               "weight": 0.6, "reasoning": "航母部署是冲突前兆"}],
                "probability_changes": [{"node_id": "us_iran_conflict", "new_probability": 0.45,
                                         "new_confidence": 0.85, "evidence": ["航母战斗群进入波斯湾"],
                                         "reasoning": "军事存在增加"}],
                "removed_nodes": [], "removed_edges": [],
            },
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])
        assert "carrier_deployment" in updated.nodes
        assert updated.nodes["us_iran_conflict"].probability == 0.45
        assert len(updated.edges) == 1

    def test_rejects_cycle(self):
        engine = DAGEngine(api_key="fake")
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={
                "a": Node(id="a", label="A", domains=["军事"], probability=0.5,
                          confidence=0.8, evidence=["t"], reasoning="t"),
                "b": Node(id="b", label="B", domains=["军事"], probability=0.3,
                          confidence=0.8, evidence=["t"], reasoning="t"),
            },
            edges=[Edge(source="a", target="b", weight=0.5, reasoning="t")],
        )
        llm_response = {
            "analysis": "test", "model_insights": [],
            "updates": {
                "new_nodes": [],
                "new_edges": [{"from": "b", "to": "a", "weight": 0.3, "reasoning": "bad cycle"}],
                "probability_changes": [], "removed_nodes": [], "removed_edges": [],
            },
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])
        assert not updated.has_cycle()
        assert len(updated.edges) == 1

    def test_empty_update(self):
        engine = DAGEngine(api_key="fake")
        dag = _sample_dag()
        llm_response = {
            "analysis": "无变化", "model_insights": [],
            "updates": {"new_nodes": [], "new_edges": [],
                        "probability_changes": [], "removed_nodes": [], "removed_edges": []},
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])
        assert len(updated.nodes) == 1
        assert updated.nodes["us_iran_conflict"].probability == 0.35
