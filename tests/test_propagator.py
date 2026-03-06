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

    def test_propagated_value_overrides_initial(self):
        """After design change: propagated value always wins for nodes with parents.
        This ensures probabilities can both rise AND fall based on parent changes."""
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.3), "b": _node("b", 0.5)},
                  edges=[Edge(source="a", target="b", weight=0.2, reasoning="t")])
        result = propagate(dag)
        # Noisy-OR: 1 - (1 - 0.3*0.2) = 0.06
        assert abs(result.nodes["b"].probability - 0.06) < 0.01

    def test_probability_can_decrease(self):
        """Key test: if parent probability drops, child should drop too."""
        dag_high = DAG(scenario="test", scenario_label="test",
                       nodes={"a": _node("a", 1.0), "b": _node("b", 0.0)},
                       edges=[Edge(source="a", target="b", weight=0.8, reasoning="t")])
        dag_low = DAG(scenario="test", scenario_label="test",
                      nodes={"a": _node("a", 0.2), "b": _node("b", 0.0)},
                      edges=[Edge(source="a", target="b", weight=0.8, reasoning="t")])
        result_high = propagate(dag_high)
        result_low = propagate(dag_low)
        assert result_high.nodes["b"].probability > result_low.nodes["b"].probability

    def test_chain_propagation(self):
        dag = DAG(scenario="test", scenario_label="test",
                  nodes={"a": _node("a", 0.8), "b": _node("b", 0.0), "c": _node("c", 0.0)},
                  edges=[Edge(source="a", target="b", weight=0.5, reasoning="t"),
                         Edge(source="b", target="c", weight=0.6, reasoning="t")])
        result = propagate(dag)
        assert abs(result.nodes["b"].probability - 0.4) < 0.01
        assert abs(result.nodes["c"].probability - 0.24) < 0.01
