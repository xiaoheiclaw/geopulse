"""Tests for report generation."""
from geopulse.models import DAG, Edge, Node
from geopulse.reporter import Reporter


def _make_dag() -> DAG:
    return DAG(
        scenario="us_iran_conflict", scenario_label="美伊冲突",
        nodes={
            "conflict": Node(id="conflict", label="美伊军事冲突", domains=["军事"],
                             probability=0.35, confidence=0.8, evidence=["test"], reasoning="root"),
            "strait": Node(id="strait", label="霍尔木兹封锁", domains=["能源", "军事"],
                           probability=0.25, confidence=0.7, evidence=["test"], reasoning="child"),
            "oil": Node(id="oil", label="油价飙升", domains=["能源", "金融"],
                        probability=0.20, confidence=0.6, evidence=["test"], reasoning="grandchild"),
        },
        edges=[
            Edge(source="conflict", target="strait", weight=0.7, reasoning="t"),
            Edge(source="strait", target="oil", weight=0.6, reasoning="t"),
        ],
    )


class TestReporter:
    def test_daily_report_structure(self):
        reporter = Reporter()
        dag = _make_dag()
        report = reporter.daily_report(dag, events_summary=["伊朗海军演习", "美国制裁声明"])
        assert "GeoPulse" in report
        assert "0阶" in report or "零阶" in report

    def test_report_contains_dag_tree(self):
        reporter = Reporter()
        dag = _make_dag()
        report = reporter.daily_report(dag)
        assert "美伊军事冲突" in report
        assert "霍尔木兹封锁" in report
        assert "油价飙升" in report

    def test_probability_changes(self):
        reporter = Reporter()
        old_dag = _make_dag()
        new_dag = _make_dag()
        new_dag.nodes["strait"].probability = 0.35
        changes = reporter.compute_changes(old_dag, new_dag, threshold=0.05)
        assert len(changes) == 1
        assert changes[0]["node_id"] == "strait"

    def test_node_detail_report(self):
        reporter = Reporter()
        dag = _make_dag()
        report = reporter.node_detail(dag, "strait")
        assert "霍尔木兹封锁" in report
        assert "0.25" in report
