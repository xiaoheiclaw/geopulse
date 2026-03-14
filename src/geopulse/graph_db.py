"""GeoPulse Graph Database — NetworkX + SQLite backend.

Provides:
1. DAG as a queryable directed graph (path analysis, centrality, cascades)
2. Events linked to DAG nodes (auto-matching by keyword/entity)
3. Node probability time series (from history/ snapshots)
4. Query API for the agent and scripts
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx


class GeoPulseGraph:
    """Graph database backed by NetworkX (graph ops) + SQLite (events + time series)."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.G = nx.DiGraph()
        self.db_path = self.data_dir / "geopulse.db"
        self._init_db()

    # ── Setup ──────────────────────────────────────────────

    def _init_db(self):
        """Create SQLite tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    headline TEXT NOT NULL,
                    details TEXT,
                    source_url TEXT,
                    source_name TEXT,
                    domains TEXT,  -- JSON array
                    significance INTEGER DEFAULT 3,
                    timestamp TEXT,
                    logged_at TEXT,
                    backfilled INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS event_node_links (
                    event_id INTEGER REFERENCES events(id),
                    node_id TEXT,
                    relevance REAL DEFAULT 0.5,
                    PRIMARY KEY (event_id, node_id)
                );

                CREATE TABLE IF NOT EXISTS node_history (
                    node_id TEXT,
                    timestamp TEXT,
                    probability REAL,
                    confidence REAL,
                    dag_version INTEGER,
                    PRIMARY KEY (node_id, timestamp)
                );

                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_significance ON events(significance);
                CREATE INDEX IF NOT EXISTS idx_node_history_node ON node_history(node_id);
                CREATE INDEX IF NOT EXISTS idx_event_links_node ON event_node_links(node_id);
            """)

    # ── Load ───────────────────────────────────────────────

    def load_dag(self, dag_path: str | None = None):
        """Load DAG from JSON into NetworkX graph."""
        path = Path(dag_path) if dag_path else self.data_dir / "dag.json"
        with open(path) as f:
            dag = json.load(f)

        self.G.clear()

        for nid, node in dag.get("nodes", {}).items():
            self.G.add_node(nid, **{
                "label": node.get("label", nid),
                "probability": node.get("probability", 0.5),
                "confidence": node.get("confidence", 0.5),
                "domains": node.get("domains", []),
                "evidence": node.get("evidence", []),
                "reasoning": node.get("reasoning", ""),
            })

        for edge in dag.get("edges", []):
            self.G.add_edge(
                edge["source"], edge["target"],
                weight=edge.get("weight", 0.5),
                reasoning=edge.get("reasoning", ""),
            )

        return len(self.G.nodes), len(self.G.edges)

    def load_events(self, events_path: str | None = None):
        """Load events from JSONL into SQLite."""
        path = Path(events_path) if events_path else self.data_dir / "events.jsonl"
        if not path.exists():
            return 0

        with sqlite3.connect(self.db_path) as conn:
            # Check existing count
            existing = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if existing > 0:
                return existing  # Already loaded

            count = 0
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    e = json.loads(line)
                    conn.execute(
                        """INSERT INTO events (headline, details, source_url, source_name,
                           domains, significance, timestamp, logged_at, backfilled)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            e.get("headline", ""),
                            e.get("details", ""),
                            e.get("source_url", ""),
                            e.get("source_name", ""),
                            json.dumps(e.get("domains", []), ensure_ascii=False),
                            e.get("significance", 3),
                            e.get("timestamp", ""),
                            e.get("logged_at", ""),
                            1 if e.get("backfilled") else 0,
                        ),
                    )
                    count += 1
            return count

    def load_history(self):
        """Load node probability history from history/ snapshots."""
        history_dir = self.data_dir / "history"
        if not history_dir.exists():
            return 0

        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute("SELECT COUNT(*) FROM node_history").fetchone()[0]
            if existing > 0:
                return existing

            count = 0
            for fp in sorted(history_dir.glob("*.json")):
                if fp.name.startswith("dag_"):
                    # Skip non-timestamped snapshots
                    continue
                ts = fp.stem.replace("_", ".")  # approximate timestamp from filename
                try:
                    with open(fp) as f:
                        snap = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                version = snap.get("version", 0)
                for nid, node in snap.get("nodes", {}).items():
                    prob = node.get("probability")
                    conf = node.get("confidence")
                    if prob is not None:
                        conn.execute(
                            """INSERT OR IGNORE INTO node_history
                               (node_id, timestamp, probability, confidence, dag_version)
                               VALUES (?, ?, ?, ?, ?)""",
                            (nid, ts, prob, conf, version),
                        )
                        count += 1
            return count

    # ── Auto-link events to nodes ──────────────────────────

    def auto_link_events(self):
        """Link events to DAG nodes by keyword matching on node labels + evidence."""
        if not self.G.nodes:
            return 0

        # Build keyword index: node_id -> set of keywords
        node_keywords: dict[str, set[str]] = {}
        for nid, data in self.G.nodes(data=True):
            keywords = set()
            label = data.get("label", "")
            # Split Chinese/English label into tokens
            keywords.update(w.lower() for w in re.findall(r'[a-zA-Z]+', label) if len(w) > 2)
            keywords.update(re.findall(r'[\u4e00-\u9fff]+', label))
            # Add node_id parts
            keywords.update(w.lower() for w in nid.split("_") if len(w) > 2)
            # Add evidence keywords
            for ev in data.get("evidence", []):
                if isinstance(ev, str):
                    keywords.update(w.lower() for w in re.findall(r'[a-zA-Z]+', ev) if len(w) > 3)
            node_keywords[nid] = keywords

        linked = 0
        with sqlite3.connect(self.db_path) as conn:
            events = conn.execute(
                "SELECT id, headline, details FROM events"
            ).fetchall()

            for eid, headline, details in events:
                text = f"{headline} {details}".lower()
                text_cn = headline + " " + (details or "")

                for nid, keywords in node_keywords.items():
                    matches = sum(1 for kw in keywords if kw in text or kw in text_cn)
                    if matches >= 2:  # At least 2 keyword matches
                        relevance = min(matches / len(keywords), 1.0) if keywords else 0
                        try:
                            conn.execute(
                                """INSERT OR IGNORE INTO event_node_links
                                   (event_id, node_id, relevance)
                                   VALUES (?, ?, ?)""",
                                (eid, nid, round(relevance, 3)),
                            )
                            linked += 1
                        except sqlite3.IntegrityError:
                            pass
        return linked

    # ── Query: Graph Analysis ──────────────────────────────

    def shortest_path(self, source: str, target: str) -> list[dict]:
        """Find shortest causal path between two nodes."""
        try:
            path = nx.shortest_path(self.G, source, target)
            result = []
            for i, nid in enumerate(path):
                entry = {
                    "node": nid,
                    "label": self.G.nodes[nid].get("label", nid),
                    "probability": self.G.nodes[nid].get("probability"),
                }
                if i > 0:
                    edge = self.G.edges[path[i - 1], nid]
                    entry["edge_weight"] = edge.get("weight")
                    entry["edge_reasoning"] = edge.get("reasoning", "")
                result.append(entry)
            return result
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            return []

    def all_paths(self, source: str, target: str, max_length: int = 6) -> list[list[str]]:
        """Find all simple paths between two nodes."""
        try:
            return list(nx.all_simple_paths(self.G, source, target, cutoff=max_length))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def cascade_impact(self, node_id: str, depth: int = 3) -> dict[str, float]:
        """Calculate cascade impact: what nodes are downstream and how much."""
        if node_id not in self.G:
            return {}

        impacts: dict[str, float] = {}
        visited = {node_id}
        frontier = [(node_id, 1.0)]

        for _ in range(depth):
            next_frontier = []
            for nid, cumulative in frontier:
                for succ in self.G.successors(nid):
                    if succ in visited:
                        continue
                    weight = self.G.edges[nid, succ].get("weight", 0.5)
                    impact = cumulative * weight
                    if impact > 0.01:  # threshold
                        impacts[succ] = max(impacts.get(succ, 0), impact)
                        next_frontier.append((succ, impact))
                        visited.add(succ)
            frontier = next_frontier

        return dict(sorted(impacts.items(), key=lambda x: -x[1]))

    def bottleneck_nodes(self, top_n: int = 10) -> list[dict]:
        """Find bottleneck nodes by betweenness centrality."""
        centrality = nx.betweenness_centrality(self.G)
        sorted_nodes = sorted(centrality.items(), key=lambda x: -x[1])[:top_n]
        return [
            {
                "node": nid,
                "label": self.G.nodes[nid].get("label", nid),
                "centrality": round(c, 4),
                "probability": self.G.nodes[nid].get("probability"),
                "in_degree": self.G.in_degree(nid),
                "out_degree": self.G.out_degree(nid),
            }
            for nid, c in sorted_nodes
        ]

    def domain_subgraph(self, domain: str) -> list[str]:
        """Get all nodes in a specific domain."""
        return [
            nid for nid, data in self.G.nodes(data=True)
            if domain in data.get("domains", [])
        ]

    # ── Query: Events ──────────────────────────────────────

    def events_for_node(self, node_id: str, limit: int = 20) -> list[dict]:
        """Get events linked to a specific DAG node."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT e.headline, e.details, e.source_url, e.timestamp,
                          e.significance, l.relevance
                   FROM events e
                   JOIN event_node_links l ON e.id = l.event_id
                   WHERE l.node_id = ?
                   ORDER BY e.significance DESC, l.relevance DESC
                   LIMIT ?""",
                (node_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def events_by_date(self, date: str, min_significance: int = 3) -> list[dict]:
        """Get events for a specific date."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT headline, details, source_url, source_name,
                          significance, timestamp
                   FROM events
                   WHERE timestamp LIKE ? AND significance >= ?
                   ORDER BY significance DESC""",
                (f"{date}%", min_significance),
            ).fetchall()
            return [dict(r) for r in rows]

    def event_count_by_date(self) -> dict[str, int]:
        """Get event count per day."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT SUBSTR(COALESCE(timestamp, logged_at), 1, 10) as day,
                          COUNT(*) as cnt
                   FROM events
                   GROUP BY day ORDER BY day"""
            ).fetchall()
            return {r[0]: r[1] for r in rows}

    # ── Query: Time Series ─────────────────────────────────

    def node_probability_history(self, node_id: str) -> list[dict]:
        """Get probability history for a node."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT timestamp, probability, confidence, dag_version
                   FROM node_history
                   WHERE node_id = ?
                   ORDER BY timestamp""",
                (node_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def biggest_movers(self, last_n_versions: int = 5) -> list[dict]:
        """Find nodes with largest probability changes in recent versions."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """WITH ranked AS (
                     SELECT node_id, probability, dag_version,
                            ROW_NUMBER() OVER (PARTITION BY node_id ORDER BY timestamp DESC) as rn
                     FROM node_history
                   )
                   SELECT a.node_id,
                          a.probability as current_prob,
                          b.probability as old_prob,
                          ABS(a.probability - b.probability) as delta
                   FROM ranked a
                   JOIN ranked b ON a.node_id = b.node_id
                   WHERE a.rn = 1 AND b.rn = ?
                   ORDER BY delta DESC
                   LIMIT 15""",
                (last_n_versions,),
            ).fetchall()
            return [
                {
                    "node": r[0],
                    "current": round(r[1], 3),
                    "old": round(r[2], 3),
                    "delta": round(r[3], 3),
                }
                for r in rows
            ]

    # ── Summary ────────────────────────────────────────────

    def summary(self) -> dict:
        """Get database summary stats."""
        with sqlite3.connect(self.db_path) as conn:
            events_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            links_count = conn.execute("SELECT COUNT(*) FROM event_node_links").fetchone()[0]
            history_count = conn.execute("SELECT COUNT(*) FROM node_history").fetchone()[0]

        return {
            "nodes": len(self.G.nodes),
            "edges": len(self.G.edges),
            "events": events_count,
            "event_node_links": links_count,
            "history_snapshots": history_count,
            "components": nx.number_weakly_connected_components(self.G),
            "density": round(nx.density(self.G), 4),
            "avg_clustering": round(
                nx.average_clustering(self.G.to_undirected()), 4
            ) if len(self.G) > 0 else 0,
        }


def init_graph(data_dir: str = "data") -> GeoPulseGraph:
    """Initialize and load everything."""
    g = GeoPulseGraph(data_dir)
    nodes, edges = g.load_dag()
    events = g.load_events()
    history = g.load_history()
    links = g.auto_link_events()
    print(f"Graph loaded: {nodes}N/{edges}E, {events} events, {history} history points, {links} links")
    return g
