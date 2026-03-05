"""Data models for GeoPulse DAG and events."""
from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Node(BaseModel):
    """A node in the causal DAG representing an event or condition."""
    id: str
    label: str
    domains: list[str]
    probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = ""
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Edge(BaseModel):
    """A directed edge representing a causal relationship."""
    source: str
    target: str
    weight: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class Event(BaseModel):
    """A structured event extracted from a news article."""
    headline: str
    details: str = ""
    entities: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    source_url: str = ""
    timestamp: datetime | None = None
    significance: int = Field(default=3, ge=1, le=5)


class DAG(BaseModel):
    """The causal probability network."""
    scenario: str
    scenario_label: str
    version: int = 1
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)

    def root_nodes(self) -> list[str]:
        """Return node IDs with no incoming edges."""
        targets = {e.target for e in self.edges}
        return [nid for nid in self.nodes if nid not in targets]

    def parent_nodes(self, node_id: str) -> list[str]:
        """Return IDs of nodes with edges pointing to node_id."""
        return [e.source for e in self.edges if e.target == node_id]

    def child_nodes(self, node_id: str) -> list[str]:
        """Return IDs of nodes that node_id has edges pointing to."""
        return [e.target for e in self.edges if e.source == node_id]

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological ordering."""
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)
        for e in self.edges:
            in_degree[e.target] += 1
            adj[e.source].append(e.target)
        for nid in self.nodes:
            in_degree.setdefault(nid, 0)
        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []
        while queue:
            nid = queue.popleft()
            result.append(nid)
            for child in adj[nid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        return result

    def has_cycle(self) -> bool:
        """Return True if the DAG contains a cycle."""
        return len(self.topological_sort()) != len(self.nodes)

    def compute_orders(self) -> dict[str, int]:
        """Compute order (causal distance from root) for each node."""
        orders: dict[str, int] = {}
        for nid in self.topological_sort():
            parents = self.parent_nodes(nid)
            if not parents:
                orders[nid] = 0
            else:
                orders[nid] = min(orders.get(p, 0) for p in parents) + 1
        return orders

    def global_risk_index(self) -> float:
        """Compute a weighted average risk index (0-100)."""
        if not self.nodes:
            return 0.0
        total = sum(n.probability * n.confidence for n in self.nodes.values())
        weight = sum(n.confidence for n in self.nodes.values())
        return round((total / weight) * 100, 1) if weight > 0 else 0.0

    def to_json(self) -> str:
        """Serialize DAG to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, data: str) -> DAG:
        """Deserialize DAG from JSON string."""
        return cls.model_validate_json(data)
