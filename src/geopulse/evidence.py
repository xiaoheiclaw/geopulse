"""Evidence data model — v7.4 L1 output.

Upgrades from Event (news extraction) to Evidence (credibility-scored,
DAG-linked input for the Agent reasoning pipeline).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .models import Event


class Evidence(BaseModel):
    """A piece of evidence fed into the v7.4 pipeline.

    Starts from a news event and gets enriched by the Agent with
    credibility scoring and affected-node identification.
    """

    id: str = Field(..., description="唯一标识 (sha256 prefix of text)")
    text: str = Field(..., description="原始新闻文本（摘要）")
    source_url: str = ""
    source_type: str = ""  # "reuters" | "aljazeera" | "war_on_rocks" etc.
    domains: list[str] = Field(default_factory=list)
    timestamp: datetime | None = None
    significance: int = Field(default=3, ge=1, le=5)
    # ── Agent-populated fields ──
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    affected_nodes: list[str] = Field(default_factory=list)
    impact_direction: str = ""  # "probability_increase" | "probability_decrease" | "structural_change"


def _make_evidence_id(text: str) -> str:
    """Generate a short deterministic ID from evidence text."""
    return "ev_" + hashlib.sha256(text.encode()).hexdigest()[:12]


def _infer_source_type(url: str) -> str:
    """Best-effort source type from URL domain."""
    url_lower = url.lower()
    for domain, stype in [
        ("reuters", "reuters"),
        ("aljazeera", "aljazeera"),
        ("warontherocks", "war_on_the_rocks"),
        ("foreignaffairs", "foreign_affairs"),
        ("bbc", "bbc"),
        ("nytimes", "nytimes"),
        ("ft.com", "ft"),
    ]:
        if domain in url_lower:
            return stype
    return "unknown"


def events_to_evidence(events: list[Event]) -> list[Evidence]:
    """Convert existing Event objects to Evidence.

    credibility and affected_nodes are left at defaults — the Agent
    fills them in during L1 processing.
    """
    result: list[Evidence] = []
    for ev in events:
        text = ev.headline
        if ev.details:
            text = f"{ev.headline} — {ev.details}"
        result.append(
            Evidence(
                id=_make_evidence_id(text),
                text=text,
                source_url=ev.source_url,
                source_type=_infer_source_type(ev.source_url),
                domains=ev.domains,
                timestamp=ev.timestamp,
                significance=ev.significance,
            )
        )
    return result
