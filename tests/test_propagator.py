"""Tests for Noisy-OR probability propagation."""
import pytest
from geopulse.models import DAG, Edge, Node
from geopulse.propagator import propagate


def _node(id: str, prob: float, conf: float = 0.8, domains: list[str] | None = None) -> Node:
    return Node(id=id, label=id, domains=domains or ["军事"],
                probability=prob, confidence=conf, evidence=["test"], reasoning="test")


class TestPropagate:
    def test_single_parent(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.6), "b": _node("b", 0.0)},
                  edges=[Edge(source="a", target="b", weight=0.5, reasoning="t")])
        result = propagate(dag)
        assert abs(result.nodes["b"].probability - 0.3) < 0.01

    def test_two_parents_noisy_or(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.5), "b": _node("b", 0.4), "c": _node("c", 0.0)},
                  edges=[Edge(source="a", target="c", weight=0.6, reasoning="t"),
                         Edge(source="b", target="c", weight=0.5, reasoning="t")])
        result = propagate(dag)
        assert abs(result.nodes["c"].probability - 0.44) < 0.01

    def test_root_nodes_unchanged(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.7)}, edges=[])
        result = propagate(dag)
        assert result.nodes["a"].probability == 0.7

    def test_llm_probability_preserved_if_higher(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.3), "b": _node("b", 0.5)},
                  edges=[Edge(source="a", target="b", weight=0.2, reasoning="t")])
        result = propagate(dag)
        assert result.nodes["b"].probability == 0.5

    def test_chain_propagation(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.8), "b": _node("b", 0.0), "c": _node("c", 0.0)},
                  edges=[Edge(source="a", target="b", weight=0.5, reasoning="t"),
                         Edge(source="b", target="c", weight=0.6, reasoning="t")])
        result = propagate(dag)
        assert abs(result.nodes["b"].probability - 0.4) < 0.01
        assert abs(result.nodes["c"].probability - 0.24) < 0.01
