"""Tests for GeoPulse data models."""
import json
from datetime import datetime, timezone

import pytest

from geopulse.models import DAG, Edge, Event, Node


class TestNode:
    def test_create_node(self):
        node = Node(
            id="oil_price_surge",
            label="油价飙升",
            domains=["能源", "金融"],
            probability=0.4,
            confidence=0.7,
            evidence=["2026-03-04: WTI突破90美元"],
            reasoning="霍尔木兹海峡紧张局势推高油价",
        )
        assert node.id == "oil_price_surge"
        assert node.probability == 0.4
        assert len(node.domains) == 2

    def test_probability_range(self):
        with pytest.raises(ValueError):
            Node(
                id="bad", label="坏节点", domains=["军事"],
                probability=1.5, confidence=0.5,
                evidence=[], reasoning="test",
            )

    def test_confidence_range(self):
        with pytest.raises(ValueError):
            Node(
                id="bad", label="坏节点", domains=["军事"],
                probability=0.5, confidence=-0.1,
                evidence=[], reasoning="test",
            )


class TestEdge:
    def test_create_edge(self):
        edge = Edge(
            source="strait_closure",
            target="oil_price_surge",
            weight=0.8,
            reasoning="海峡封锁直接影响原油供应",
        )
        assert edge.source == "strait_closure"
        assert edge.target == "oil_price_surge"
        assert edge.weight == 0.8

    def test_weight_range(self):
        with pytest.raises(ValueError):
            Edge(source="a", target="b", weight=1.5, reasoning="test")


class TestDAG:
    def _make_dag(self) -> DAG:
        root = Node(
            id="us_iran_conflict", label="美伊军事冲突",
            domains=["军事"], probability=0.35, confidence=0.8,
            evidence=["test"], reasoning="root event",
        )
        child = Node(
            id="strait_closure", label="霍尔木兹封锁",
            domains=["能源", "军事"], probability=0.25, confidence=0.7,
            evidence=["test"], reasoning="consequence",
        )
        edge = Edge(
            source="us_iran_conflict", target="strait_closure",
            weight=0.7, reasoning="冲突导致封锁",
        )
        return DAG(
            scenario="us_iran_conflict",
            scenario_label="美伊冲突",
            nodes={"us_iran_conflict": root, "strait_closure": child},
            edges=[edge],
        )

    def test_root_nodes(self):
        dag = self._make_dag()
        roots = dag.root_nodes()
        assert len(roots) == 1
        assert roots[0] == "us_iran_conflict"

    def test_node_order(self):
        dag = self._make_dag()
        orders = dag.compute_orders()
        assert orders["us_iran_conflict"] == 0
        assert orders["strait_closure"] == 1

    def test_topological_sort(self):
        dag = self._make_dag()
        sorted_ids = dag.topological_sort()
        assert sorted_ids.index("us_iran_conflict") < sorted_ids.index("strait_closure")

    def test_cycle_detection(self):
        dag = self._make_dag()
        dag.edges.append(Edge(
            source="strait_closure", target="us_iran_conflict",
            weight=0.1, reasoning="cycle",
        ))
        assert dag.has_cycle() is True

    def test_no_cycle(self):
        dag = self._make_dag()
        assert dag.has_cycle() is False

    def test_parent_nodes(self):
        dag = self._make_dag()
        parents = dag.parent_nodes("strait_closure")
        assert parents == ["us_iran_conflict"]

    def test_child_nodes(self):
        dag = self._make_dag()
        children = dag.child_nodes("us_iran_conflict")
        assert children == ["strait_closure"]

    def test_json_roundtrip(self):
        dag = self._make_dag()
        json_str = dag.to_json()
        loaded = DAG.from_json(json_str)
        assert loaded.scenario == dag.scenario
        assert len(loaded.nodes) == len(dag.nodes)
        assert len(loaded.edges) == len(dag.edges)

    def test_global_risk_index(self):
        dag = self._make_dag()
        gri = dag.global_risk_index()
        assert 0 <= gri <= 100


class TestEvent:
    def test_create_event(self):
        event = Event(
            headline="伊朗海军在霍尔木兹海峡举行演习",
            details="伊朗海军出动20艘舰艇在霍尔木兹海峡举行大规模军事演习",
            entities=["伊朗", "霍尔木兹海峡"],
            domains=["军事"],
            source_url="https://example.com/article",
            significance=4,
        )
        assert event.significance == 4
        assert "伊朗" in event.entities
