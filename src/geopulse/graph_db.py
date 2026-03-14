"""GeoPulse Graph Database — NetworkX backend.

Loads DAG + events into a queryable graph with:
- Causal path analysis
- Event-node linking
- Temporal probability tracking
- Centrality & bottleneck detection
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx


class GeoPulseGraph:
    """In-memory graph database backed by NetworkX."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.G = nx.DiGraph()
        self.events: list[dict] = []
        self.event_node_links: dict[str, list[int]] = defaultdict(list)  # node_id -> [event_idx]
        self.node_event_links: dict[int, list[str]] = defaultdict(list)  # event_idx -> [node_id]

    def load(self) -> "GeoPulseGraph":
        """Load DAG + events from disk."""
        self._load_dag()
        self._load_events()
        self._link_events_to_nodes()
        return self

    def _load_dag(self):
        """Load dag.json into NetworkX DiGraph."""
        dag_path = self.data_dir / "dag.json"
        with open(dag_path) as f:
            dag = json.load(f)

        self.dag_version = dag.get("version", 0)

        for node_id, node in dag.get("nodes", {}).items():
            self.G.add_node(
                node_id,
                label=node.get("label", node_id),
                probability=node.get("probability", 0.5),
                confidence=node.get("confidence", 0.5),
                domains=node.get("domains", []),
                evidence=node.get("evidence", []),
                reasoning=node.get("reasoning", ""),
                node_type=node.get("node_type", "state"),
                last_updated=node.get("last_updated", ""),
            )

        for edge in dag.get("edges", []):
            self.G.add_edge(
                edge["source"],
                edge["target"],
                weight=edge.get("weight", 0.5),
                reasoning=edge.get("reasoning", ""),
            )

    def _load_events(self):
        """Load events.jsonl."""
        events_path = self.data_dir / "events.jsonl"
        if not events_path.exists():
            return
        with open(events_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    self.events.append(json.loads(line))

    def _link_events_to_nodes(self):
        """Auto-link events to DAG nodes via keyword matching."""
        # Build keyword index from node labels + evidence
        node_keywords: dict[str, set[str]] = {}
        for node_id, data in self.G.nodes(data=True):
            keywords = set()
            # From label
            label = data.get("label", "")
            keywords.update(self._extract_keywords(label))
            # From node_id
            keywords.update(node_id.replace("_", " ").lower().split())
            # From evidence
            for ev in data.get("evidence", []):
                if isinstance(ev, str):
                    keywords.update(self._extract_keywords(ev))
            node_keywords[node_id] = keywords

        # Match events to nodes
        for idx, event in enumerate(self.events):
            event_text = (
                event.get("headline", "") + " " + event.get("details", "")
            ).lower()
            event_words = set(event_text.split())

            for node_id, keywords in node_keywords.items():
                # Require at least 2 keyword matches for linking
                overlap = keywords & event_words
                if len(overlap) >= 2:
                    self.event_node_links[node_id].append(idx)
                    self.node_event_links[idx].append(node_id)

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """Extract meaningful keywords from text."""
        text = text.lower()
        # Remove common Chinese particles and short words
        words = re.findall(r"[a-z]{3,}", text)
        # Add Chinese key terms
        cn_terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        stopwords = {"the", "and", "for", "that", "this", "with", "from", "are", "was", "has", "have", "been"}
        return (set(words) - stopwords) | set(cn_terms)

    # ── Query Methods ──

    def shortest_path(self, source: str, target: str) -> list[dict]:
        """Find shortest causal path between two nodes."""
        try:
            path = nx.shortest_path(self.G, source, target)
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            return []

        result = []
        for i, node_id in enumerate(path):
            data = self.G.nodes[node_id]
            entry = {
                "node_id": node_id,
                "label": data.get("label", ""),
                "probability": data.get("probability", 0),
            }
            if i > 0:
                edge = self.G.edges[path[i - 1], node_id]
                entry["edge_weight"] = edge.get("weight", 0)
                entry["edge_reasoning"] = edge.get("reasoning", "")
            result.append(entry)
        return result

    def all_paths(self, source: str, target: str, max_length: int = 6) -> list[list[str]]:
        """Find all simple paths up to max_length."""
        try:
            return list(nx.all_simple_paths(self.G, source, target, cutoff=max_length))
        except nx.NodeNotFound:
            return []

    def influence_chain(self, source: str, max_depth: int = 4) -> dict[str, float]:
        """Calculate cumulative influence from source node, up to max_depth hops."""
        visited = {}
        queue = [(source, 1.0, 0)]

        while queue:
            node, cum_prob, depth = queue.pop(0)
            if depth > max_depth:
                continue
            if node in visited and visited[node] >= cum_prob:
                continue
            visited[node] = cum_prob

            for successor in self.G.successors(node):
                edge_w = self.G.edges[node, successor].get("weight", 0.5)
                new_prob = cum_prob * edge_w
                if new_prob > 0.01:  # prune negligible
                    queue.append((successor, new_prob, depth + 1))

        del visited[source]
        return dict(sorted(visited.items(), key=lambda x: -x[1]))

    def bottleneck_nodes(self, top_n: int = 10) -> list[dict]:
        """Find nodes with highest betweenness centrality (bottlenecks)."""
        bc = nx.betweenness_centrality(self.G, weight="weight")
        sorted_nodes = sorted(bc.items(), key=lambda x: -x[1])[:top_n]
        return [
            {
                "node_id": nid,
                "label": self.G.nodes[nid].get("label", ""),
                "probability": self.G.nodes[nid].get("probability", 0),
                "betweenness": score,
                "in_degree": self.G.in_degree(nid),
                "out_degree": self.G.out_degree(nid),
            }
            for nid, score in sorted_nodes
        ]

    def node_events(self, node_id: str, limit: int = 20) -> list[dict]:
        """Get events linked to a node, sorted by date."""
        indices = self.event_node_links.get(node_id, [])
        events = [self.events[i] for i in indices]
        events.sort(key=lambda e: e.get("logged_at", e.get("timestamp", "")), reverse=True)
        return events[:limit]

    def node_event_timeline(self, node_id: str) -> dict[str, int]:
        """Get event count per day for a node."""
        indices = self.event_node_links.get(node_id, [])
        by_date: dict[str, int] = defaultdict(int)
        for i in indices:
            ev = self.events[i]
            date = (ev.get("logged_at") or ev.get("timestamp", ""))[:10]
            if date:
                by_date[date] += 1
        return dict(sorted(by_date.items()))

    def event_impact(self, event_idx: int) -> list[dict]:
        """Show which DAG nodes an event is linked to."""
        node_ids = self.node_event_links.get(event_idx, [])
        return [
            {
                "node_id": nid,
                "label": self.G.nodes[nid].get("label", ""),
                "probability": self.G.nodes[nid].get("probability", 0),
            }
            for nid in node_ids
            if nid in self.G.nodes
        ]

    def domain_subgraph(self, domain: str) -> dict:
        """Extract subgraph for a specific domain."""
        nodes = [
            n for n, d in self.G.nodes(data=True)
            if domain in d.get("domains", [])
        ]
        sub = self.G.subgraph(nodes)
        return {
            "domain": domain,
            "nodes": len(sub.nodes),
            "edges": len(sub.edges),
            "avg_probability": (
                sum(d.get("probability", 0) for _, d in sub.nodes(data=True)) / len(sub.nodes)
                if sub.nodes else 0
            ),
            "top_nodes": sorted(
                [
                    {"id": n, "label": d.get("label", ""), "prob": d.get("probability", 0)}
                    for n, d in sub.nodes(data=True)
                ],
                key=lambda x: -x["prob"],
            )[:10],
        }

    def search_events(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across events."""
        query_lower = query.lower()
        results = []
        for idx, ev in enumerate(self.events):
            text = (ev.get("headline", "") + " " + ev.get("details", "")).lower()
            if query_lower in text:
                results.append({**ev, "_idx": idx})
        results.sort(key=lambda e: e.get("logged_at", e.get("timestamp", "")), reverse=True)
        return results[:limit]

    def stats(self) -> dict:
        """Overall graph statistics."""
        probs = [d.get("probability", 0) for _, d in self.G.nodes(data=True)]
        events_by_date = defaultdict(int)
        for ev in self.events:
            d = (ev.get("logged_at") or ev.get("timestamp", ""))[:10]
            if d:
                events_by_date[d] += 1

        linked_events = sum(1 for idx in range(len(self.events)) if idx in self.node_event_links)

        return {
            "dag_version": self.dag_version,
            "nodes": len(self.G.nodes),
            "edges": len(self.G.edges),
            "events_total": len(self.events),
            "events_linked": linked_events,
            "events_by_date": dict(sorted(events_by_date.items())),
            "avg_probability": sum(probs) / len(probs) if probs else 0,
            "density": nx.density(self.G),
            "is_dag": nx.is_directed_acyclic_graph(self.G),
            "connected_components": nx.number_weakly_connected_components(self.G),
        }
