"""Tests for Evidence data model and Event-to-Evidence conversion."""
from datetime import datetime, timezone

from geopulse.evidence import Evidence, events_to_evidence, _make_evidence_id, _infer_source_type
from geopulse.models import Event


def test_evidence_creation():
    ev = Evidence(
        id="ev_test123",
        text="Iran announces new sanctions response",
        source_url="https://reuters.com/article/123",
        source_type="reuters",
        domains=["政治", "经济"],
        significance=4,
    )
    assert ev.id == "ev_test123"
    assert ev.credibility == 0.5  # default
    assert ev.affected_nodes == []  # default empty
    assert ev.impact_direction == ""


def test_evidence_credibility_bounds():
    ev = Evidence(id="ev_1", text="test", credibility=0.0)
    assert ev.credibility == 0.0
    ev2 = Evidence(id="ev_2", text="test", credibility=1.0)
    assert ev2.credibility == 1.0


def test_make_evidence_id_deterministic():
    id1 = _make_evidence_id("same text")
    id2 = _make_evidence_id("same text")
    assert id1 == id2
    assert id1.startswith("ev_")
    assert len(id1) == 15  # "ev_" + 12 hex chars


def test_make_evidence_id_different_text():
    id1 = _make_evidence_id("text one")
    id2 = _make_evidence_id("text two")
    assert id1 != id2


def test_infer_source_type():
    assert _infer_source_type("https://reuters.com/article/123") == "reuters"
    assert _infer_source_type("https://www.aljazeera.com/news") == "aljazeera"
    assert _infer_source_type("https://warontherocks.com/2026/03") == "war_on_the_rocks"
    assert _infer_source_type("https://unknown-site.com") == "unknown"
    assert _infer_source_type("") == "unknown"


def test_events_to_evidence_basic():
    events = [
        Event(
            headline="Iran test-fires missile",
            details="medium-range ballistic missile test",
            entities=["Iran", "IRGC"],
            domains=["军事"],
            source_url="https://reuters.com/art/1",
            significance=4,
        ),
    ]
    evidence = events_to_evidence(events)
    assert len(evidence) == 1
    ev = evidence[0]
    assert "Iran test-fires missile" in ev.text
    assert "medium-range ballistic missile test" in ev.text
    assert ev.source_type == "reuters"
    assert ev.domains == ["军事"]
    assert ev.significance == 4
    assert ev.credibility == 0.5  # default, for Agent to fill
    assert ev.affected_nodes == []  # default, for Agent to fill


def test_events_to_evidence_no_details():
    events = [Event(headline="Brief headline", domains=["政治"])]
    evidence = events_to_evidence(events)
    assert len(evidence) == 1
    assert evidence[0].text == "Brief headline"


def test_events_to_evidence_empty():
    evidence = events_to_evidence([])
    assert evidence == []


def test_events_to_evidence_preserves_timestamp():
    ts = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    events = [Event(headline="test", timestamp=ts)]
    evidence = events_to_evidence(events)
    assert evidence[0].timestamp == ts


def test_evidence_serialization_roundtrip():
    ev = Evidence(
        id="ev_abc",
        text="test text",
        credibility=0.8,
        affected_nodes=["node_1", "node_2"],
        impact_direction="probability_increase",
    )
    data = ev.model_dump(mode="json")
    ev2 = Evidence.model_validate(data)
    assert ev2.id == ev.id
    assert ev2.credibility == 0.8
    assert ev2.affected_nodes == ["node_1", "node_2"]
    assert ev2.impact_direction == "probability_increase"
