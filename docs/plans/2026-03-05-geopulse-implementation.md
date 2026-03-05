# GeoPulse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a geopolitical risk probability tracking system that maintains a Bayesian DAG, ingests news via Readwise, updates probabilities via LLM with mental models, and reports via OpenClaw Telegram.

**Architecture:** Event-driven pipeline (Ingester → Analyzer → DAG Engine → Propagator → Reporter) with JSON file storage. Runs as an OpenClaw agent. Noisy-OR probability propagation. Mental models library injected into LLM prompts.

**Tech Stack:** Python 3.12+, httpx (Readwise API), anthropic SDK (Claude API), pydantic (data models), pytest

**Reference:** Full design at `docs/plans/2026-03-05-geopulse-design.md`

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/geopulse/__init__.py`
- Create: `src/geopulse/py.typed`
- Create: `configs/config.yaml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `data/.gitkeep`
- Create: `data/history/.gitkeep`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "geopulse"
version = "0.1.0"
description = "Geopolitical risk probability tracking system with Bayesian DAG"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "anthropic>=0.43",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[project.scripts]
geopulse = "geopulse.cli:main"

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create config.yaml**

```yaml
# GeoPulse configuration
readwise:
  proxy: "http://127.0.0.1:7890"
  timeout: 30
  tag: "geopulse"  # Readwise tag to filter articles

llm:
  model: "claude-sonnet-4-6"
  max_tokens: 4096
  temperature: 0.3

dag:
  data_dir: "data"
  history_retention_days: 30
  max_nodes: 100  # prevent DAG from growing unbounded

report:
  min_probability_change: 0.05  # only report changes >= 5%

scenario:
  id: "us_iran_conflict"
  label: "美伊冲突"
  description: "美国-伊朗军事冲突及其全球传导影响"

domains:
  - 军事
  - 能源
  - 经济
  - 科技
  - 金融
  - 政治
  - 社会
```

**Step 3: Create .env.example**

```
READWISE_TOKEN=your_readwise_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

**Step 4: Create .gitignore**

```
data/dag.json
data/events.jsonl
data/history/*.json
.env
__pycache__/
*.pyc
.pytest_cache/
dist/
*.egg-info/
```

**Step 5: Create __init__.py**

```python
"""GeoPulse — Geopolitical risk probability tracking system."""
```

**Step 6: Install project**

Run: `cd ~/Projects/geopulse && pip install -e ".[dev]"`

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: project scaffold with pyproject.toml and config"
```

---

### Task 2: Data Models (Pydantic)

**Files:**
- Create: `src/geopulse/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/test_models.py
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
        """Helper to create a small test DAG."""
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
        # Add a back edge to create a cycle
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
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/geopulse && pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopulse.models'`

**Step 3: Implement models.py**

```python
# src/geopulse/models.py
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

    source: str  # from node id
    target: str  # to node id
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
        """Return node IDs with no incoming edges (in-degree 0)."""
        targets = {e.target for e in self.edges}
        return [nid for nid in self.nodes if nid not in targets]

    def parent_nodes(self, node_id: str) -> list[str]:
        """Return IDs of nodes with edges pointing to node_id."""
        return [e.source for e in self.edges if e.target == node_id]

    def child_nodes(self, node_id: str) -> list[str]:
        """Return IDs of nodes that node_id points to."""
        return [e.target for e in self.edges if e.source == node_id]

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological ordering."""
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)
        for e in self.edges:
            in_degree[e.target] += 1
            adj[e.source].append(e.target)
        # Ensure all nodes appear
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
        """Weighted average probability scaled to 0-100."""
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
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/geopulse && pytest tests/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/models.py tests/test_models.py
git commit -m "feat: data models with DAG topology operations"
```

---

### Task 3: Propagator (Noisy-OR)

**Files:**
- Create: `src/geopulse/propagator.py`
- Create: `tests/test_propagator.py`

**Step 1: Write the failing tests**

```python
# tests/test_propagator.py
"""Tests for Noisy-OR probability propagation."""
import pytest

from geopulse.models import DAG, Edge, Node
from geopulse.propagator import propagate


def _node(id: str, prob: float, conf: float = 0.8, domains: list[str] | None = None) -> Node:
    return Node(
        id=id, label=id, domains=domains or ["军事"],
        probability=prob, confidence=conf,
        evidence=["test"], reasoning="test",
    )


class TestPropagate:
    def test_single_parent(self):
        """P(B) = 1 - (1 - P(A)*W(A→B)) = P(A)*W"""
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={
                "a": _node("a", 0.6),
                "b": _node("b", 0.0),  # LLM gave 0, propagation should override
            },
            edges=[Edge(source="a", target="b", weight=0.5, reasoning="t")],
        )
        result = propagate(dag)
        # P(b) = 1 - (1 - 0.6*0.5) = 0.3
        assert abs(result.nodes["b"].probability - 0.3) < 0.01

    def test_two_parents_noisy_or(self):
        """P(C) = 1 - (1-P(A)*W1)(1-P(B)*W2)"""
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={
                "a": _node("a", 0.5),
                "b": _node("b", 0.4),
                "c": _node("c", 0.0),
            },
            edges=[
                Edge(source="a", target="c", weight=0.6, reasoning="t"),
                Edge(source="b", target="c", weight=0.5, reasoning="t"),
            ],
        )
        result = propagate(dag)
        # P(c) = 1 - (1-0.5*0.6)(1-0.4*0.5) = 1 - 0.7*0.8 = 0.44
        assert abs(result.nodes["c"].probability - 0.44) < 0.01

    def test_root_nodes_unchanged(self):
        """Root node probability should not be modified by propagation."""
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={"a": _node("a", 0.7)},
            edges=[],
        )
        result = propagate(dag)
        assert result.nodes["a"].probability == 0.7

    def test_llm_probability_preserved_if_higher(self):
        """If LLM assigned a higher prob than propagation, keep LLM value."""
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={
                "a": _node("a", 0.3),
                "b": _node("b", 0.5),  # LLM says 0.5
            },
            edges=[Edge(source="a", target="b", weight=0.2, reasoning="t")],
        )
        result = propagate(dag)
        # Propagated = 0.3*0.2 = 0.06, LLM = 0.5, keep 0.5
        assert result.nodes["b"].probability == 0.5

    def test_chain_propagation(self):
        """A→B→C should propagate through the chain."""
        dag = DAG(
            scenario="test", scenario_label="test",
            nodes={
                "a": _node("a", 0.8),
                "b": _node("b", 0.0),
                "c": _node("c", 0.0),
            },
            edges=[
                Edge(source="a", target="b", weight=0.5, reasoning="t"),
                Edge(source="b", target="c", weight=0.6, reasoning="t"),
            ],
        )
        result = propagate(dag)
        # P(b) = 0.8*0.5 = 0.4
        assert abs(result.nodes["b"].probability - 0.4) < 0.01
        # P(c) = 0.4*0.6 = 0.24
        assert abs(result.nodes["c"].probability - 0.24) < 0.01
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/geopulse && pytest tests/test_propagator.py -v`
Expected: FAIL

**Step 3: Implement propagator.py**

```python
# src/geopulse/propagator.py
"""Noisy-OR probability propagation on the DAG."""
from __future__ import annotations

import copy

from .models import DAG


def propagate(dag: DAG) -> DAG:
    """Propagate probabilities through the DAG using Noisy-OR.

    For each non-root node, computes:
        P(B) = 1 - ∏(1 - P(Ai) * W(Ai→B))  for all parent Ai

    Keeps the higher of LLM-assigned and propagated probability.
    Returns a new DAG with updated probabilities (does not mutate input).
    """
    result = dag.model_copy(deep=True)

    # Build edge lookup: target → [(source, weight)]
    parents_map: dict[str, list[tuple[str, float]]] = {}
    for edge in result.edges:
        parents_map.setdefault(edge.target, []).append((edge.source, edge.weight))

    # Store original LLM probabilities
    llm_probs = {nid: n.probability for nid, n in result.nodes.items()}

    for nid in result.topological_sort():
        if nid not in parents_map:
            continue  # root node, keep LLM probability

        product = 1.0
        for parent_id, weight in parents_map[nid]:
            parent_prob = result.nodes[parent_id].probability
            product *= (1.0 - parent_prob * weight)

        propagated = 1.0 - product
        result.nodes[nid].probability = max(llm_probs[nid], round(propagated, 4))

    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/geopulse && pytest tests/test_propagator.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/propagator.py tests/test_propagator.py
git commit -m "feat: Noisy-OR probability propagation"
```

---

### Task 4: Mental Models Library

**Files:**
- Create: `models/counterfactual.md`
- Create: `models/deterrence.md`
- Create: `models/brinkmanship.md`
- Create: `models/focal_points.md`
- Create: `models/second_order.md`
- Create: `models/fog_of_war.md`
- Create: `models/sunk_cost_escalation.md`
- Create: `models/asymmetric_conflict.md`
- Create: `src/geopulse/mental_models.py`
- Create: `tests/test_mental_models.py`

**Step 1: Create all 8 mental model .md files**

Each file follows the format from design doc Appendix A. Full content is in the design doc at `docs/plans/2026-03-05-geopulse-design.md` section 5 and Appendix A. Key addition: each file must have a `## Prompt 注入模板` section that can be extracted programmatically.

Example (`models/deterrence.md`):

```markdown
# 威慑理论 (Deterrence Theory)

## 来源
Thomas Schelling, *The Strategy of Conflict*

## 核心问题
威胁是否可信？承诺是否绑定？

## 分析框架
1. 威胁方的能力（capability）
2. 威胁的可信度（credibility）— 执行成本 vs 不执行的声誉损失
3. 对方的退出选项（off-ramps）
4. 观众成本（audience cost）— 公开承诺后退缩的政治代价

## Prompt 注入模板
当分析涉及威胁、制裁、最后通牒、军事部署时，考虑：
- 这个威胁可信吗？发出方愿意承受执行成本吗？
- 对方有没有"台阶下"（off-ramp）？
- 公开声明是否锁死了退路（观众成本）？
- 不执行威胁的声誉损失有多大？
```

**Step 2: Write failing tests for mental_models.py**

```python
# tests/test_mental_models.py
"""Tests for mental models loading."""
from pathlib import Path

from geopulse.mental_models import load_models, build_prompt_injection


class TestLoadModels:
    def test_loads_all_models(self):
        models = load_models()
        assert len(models) == 8

    def test_model_has_required_fields(self):
        models = load_models()
        for name, model in models.items():
            assert "title" in model
            assert "prompt_template" in model
            assert len(model["prompt_template"]) > 0


class TestBuildPromptInjection:
    def test_returns_string(self):
        result = build_prompt_injection()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_all_model_names(self):
        result = build_prompt_injection()
        assert "威慑理论" in result
        assert "反事实" in result
        assert "边缘策略" in result
```

**Step 3: Run tests to verify they fail**

Run: `cd ~/Projects/geopulse && pytest tests/test_mental_models.py -v`
Expected: FAIL

**Step 4: Implement mental_models.py**

```python
# src/geopulse/mental_models.py
"""Load and inject mental models into LLM prompts."""
from __future__ import annotations

import re
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def load_models(models_dir: Path | None = None) -> dict[str, dict[str, str]]:
    """Load all .md mental model files, extract title and prompt template."""
    directory = models_dir or MODELS_DIR
    models: dict[str, dict[str, str]] = {}

    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem

        # Extract prompt template section
        prompt_match = re.search(
            r"## Prompt 注入模板\s*\n(.*?)(?=\n## |\Z)",
            content,
            re.DOTALL,
        )
        prompt_template = prompt_match.group(1).strip() if prompt_match else ""

        models[path.stem] = {
            "title": title,
            "prompt_template": prompt_template,
            "full_content": content,
        }

    return models


def build_prompt_injection(models_dir: Path | None = None) -> str:
    """Build the combined prompt injection string from all models."""
    models = load_models(models_dir)
    sections: list[str] = []
    for name, model in models.items():
        sections.append(f"### {model['title']}\n{model['prompt_template']}")
    return "\n\n".join(sections)
```

**Step 5: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_mental_models.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
cd ~/Projects/geopulse
git add models/ src/geopulse/mental_models.py tests/test_mental_models.py
git commit -m "feat: mental models library with 8 frameworks"
```

---

### Task 5: DAG Persistence (Load/Save/History)

**Files:**
- Create: `src/geopulse/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write failing tests**

```python
# tests/test_storage.py
"""Tests for DAG persistence."""
from pathlib import Path

import pytest

from geopulse.models import DAG, Edge, Node
from geopulse.storage import DAGStorage


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def storage(tmp_data_dir):
    return DAGStorage(data_dir=tmp_data_dir)


@pytest.fixture
def sample_dag():
    return DAG(
        scenario="test", scenario_label="test",
        nodes={
            "a": Node(
                id="a", label="A", domains=["军事"],
                probability=0.5, confidence=0.8,
                evidence=["test"], reasoning="test",
            ),
        },
        edges=[],
    )


class TestDAGStorage:
    def test_save_and_load(self, storage, sample_dag):
        storage.save(sample_dag)
        loaded = storage.load()
        assert loaded is not None
        assert loaded.scenario == "test"
        assert len(loaded.nodes) == 1

    def test_load_returns_none_when_empty(self, storage):
        assert storage.load() is None

    def test_save_creates_history_snapshot(self, storage, sample_dag):
        storage.save(sample_dag)
        history = storage.list_history()
        assert len(history) == 1

    def test_increments_version(self, storage, sample_dag):
        storage.save(sample_dag)
        storage.save(sample_dag)
        loaded = storage.load()
        assert loaded.version == 2
        assert len(storage.list_history()) == 2

    def test_load_history_snapshot(self, storage, sample_dag):
        storage.save(sample_dag)
        snapshots = storage.list_history()
        loaded = storage.load_snapshot(snapshots[0])
        assert loaded.scenario == "test"
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_storage.py -v`

**Step 3: Implement storage.py**

```python
# src/geopulse/storage.py
"""DAG persistence: save, load, history snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import DAG


class DAGStorage:
    """Manages DAG persistence to JSON files."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.dag_path = self.data_dir / "dag.json"
        self.history_dir = self.data_dir / "history"

    def save(self, dag: DAG) -> Path:
        """Save DAG to disk and create a history snapshot."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Increment version if existing
        existing = self.load()
        if existing is not None:
            dag.version = existing.version + 1

        dag.updated = datetime.now(timezone.utc)

        # Write current state
        self.dag_path.write_text(dag.to_json(), encoding="utf-8")

        # Write history snapshot
        ts = dag.updated.strftime("%Y-%m-%dT%H%M%S")
        snapshot_path = self.history_dir / f"{ts}.json"
        snapshot_path.write_text(dag.to_json(), encoding="utf-8")

        return self.dag_path

    def load(self) -> DAG | None:
        """Load current DAG from disk. Returns None if not found."""
        if not self.dag_path.exists():
            return None
        return DAG.from_json(self.dag_path.read_text(encoding="utf-8"))

    def list_history(self) -> list[str]:
        """List all history snapshot filenames, sorted newest first."""
        if not self.history_dir.exists():
            return []
        return sorted(
            (p.name for p in self.history_dir.glob("*.json")),
            reverse=True,
        )

    def load_snapshot(self, filename: str) -> DAG:
        """Load a specific history snapshot."""
        path = self.history_dir / filename
        return DAG.from_json(path.read_text(encoding="utf-8"))
```

**Step 4: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_storage.py -v`

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/storage.py tests/test_storage.py
git commit -m "feat: DAG persistence with history snapshots"
```

---

### Task 6: Ingester (Readwise)

**Files:**
- Create: `src/geopulse/ingester.py`
- Create: `tests/test_ingester.py`

**Step 1: Write failing tests**

```python
# tests/test_ingester.py
"""Tests for Readwise ingester."""
from unittest.mock import MagicMock, patch

import pytest

from geopulse.ingester import ReadwiseIngester


class TestReadwiseIngester:
    def test_filter_by_tag(self):
        """Should only return articles with the geopulse tag."""
        mock_docs = [
            {"id": "1", "title": "Iran test", "tags": {"geopulse": {}}, "summary": "test", "source_url": "http://a"},
            {"id": "2", "title": "Unrelated", "tags": {"other": {}}, "summary": "test", "source_url": "http://b"},
        ]
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=mock_docs):
            articles = ingester.fetch()
        assert len(articles) == 1
        assert articles[0]["title"] == "Iran test"

    def test_empty_response(self):
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=[]):
            articles = ingester.fetch()
        assert articles == []

    def test_article_structure(self):
        """Returned articles should have required keys."""
        mock_docs = [
            {"id": "1", "title": "Test", "tags": {"geopulse": {}}, "summary": "content", "source_url": "http://a", "category": "article"},
        ]
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=mock_docs):
            articles = ingester.fetch()
        assert "title" in articles[0]
        assert "summary" in articles[0]
        assert "source_url" in articles[0]
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_ingester.py -v`

**Step 3: Implement ingester.py**

```python
# src/geopulse/ingester.py
"""Readwise Reader ingester for GeoPulse."""
from __future__ import annotations

import time
from typing import Any

import httpx

READWISE_API_BASE = "https://readwise.io/api/v3"


class ReadwiseIngester:
    """Fetches articles from Readwise Reader API, filtered by tag."""

    def __init__(
        self,
        token: str,
        tag: str = "geopulse",
        proxy: str | None = "http://127.0.0.1:7890",
        timeout: float = 30.0,
    ):
        self.token = token
        self.tag = tag
        self.proxy = proxy
        self.timeout = timeout

    def fetch(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch articles with the geopulse tag."""
        docs = self._fetch_documents(limit=limit)
        return [d for d in docs if self.tag in (d.get("tags") or {})]

    def _fetch_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch documents from Readwise API with pagination."""
        all_docs: list[dict[str, Any]] = []
        cursor: str | None = None
        headers = {"Authorization": f"Token {self.token}"}

        with httpx.Client(proxy=self.proxy, timeout=self.timeout) as client:
            while len(all_docs) < limit:
                params: dict[str, Any] = {
                    "page_size": min(limit - len(all_docs), 100),
                    "location": "new",
                }
                if cursor:
                    params["pageCursor"] = cursor

                resp = client.get(
                    f"{READWISE_API_BASE}/list/",
                    headers=headers,
                    params=params,
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "60"))
                    time.sleep(wait)
                    continue
                resp.raise_for_status()

                data = resp.json()
                all_docs.extend(data.get("results", []))
                cursor = data.get("nextPageCursor")
                if not cursor:
                    break

        return all_docs
```

**Step 4: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_ingester.py -v`

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/ingester.py tests/test_ingester.py
git commit -m "feat: Readwise ingester with tag filtering"
```

---

### Task 7: Analyzer (LLM Event Extraction)

**Files:**
- Create: `src/geopulse/analyzer.py`
- Create: `tests/test_analyzer.py`

**Step 1: Write failing tests**

```python
# tests/test_analyzer.py
"""Tests for LLM event analyzer."""
import json
from unittest.mock import MagicMock, patch

import pytest

from geopulse.analyzer import EventAnalyzer
from geopulse.models import Event


class TestEventAnalyzer:
    def _mock_llm_response(self, events_json: list[dict]) -> MagicMock:
        """Create a mock Anthropic response."""
        mock_resp = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps(events_json, ensure_ascii=False)
        mock_resp.content = [mock_block]
        return mock_resp

    def test_extracts_events(self):
        analyzer = EventAnalyzer(api_key="fake")
        mock_events = [
            {
                "headline": "伊朗宣布恢复高浓度铀浓缩",
                "details": "伊朗原子能组织宣布将浓缩铀纯度提升至60%",
                "entities": ["伊朗", "IAEA"],
                "domains": ["军事", "政治"],
                "source_url": "http://example.com",
                "significance": 4,
            }
        ]
        with patch.object(analyzer, "_call_llm", return_value=mock_events):
            events = analyzer.analyze({
                "title": "Iran resumes enrichment",
                "summary": "Iran announces 60% enrichment",
                "source_url": "http://example.com",
            })
        assert len(events) == 1
        assert isinstance(events[0], Event)
        assert events[0].significance == 4

    def test_filters_irrelevant(self):
        analyzer = EventAnalyzer(api_key="fake")
        with patch.object(analyzer, "_call_llm", return_value=[]):
            events = analyzer.analyze({
                "title": "Apple releases new iPhone",
                "summary": "Tech product launch",
                "source_url": "http://example.com",
            })
        assert events == []

    def test_handles_malformed_llm_output(self):
        analyzer = EventAnalyzer(api_key="fake")
        with patch.object(analyzer, "_call_llm", side_effect=ValueError("bad json")):
            events = analyzer.analyze({
                "title": "test",
                "summary": "test",
                "source_url": "http://example.com",
            })
        assert events == []
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_analyzer.py -v`

**Step 3: Implement analyzer.py**

```python
# src/geopulse/analyzer.py
"""LLM-based event extraction from news articles."""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from .models import Event

ANALYZER_SYSTEM_PROMPT = """\
你是一个新闻事件提取器。从以下文章中提取与"美伊冲突"相关的结构化事件。

如果文章与美伊冲突无关，返回空 JSON 列表 []。
如果是纯情绪/标题党/没有实质信息，返回空列表 []。

每个事件输出为 JSON 数组中的对象：
[
  {
    "headline": "事件一句话描述（≤30字）",
    "details": "关键细节（≤100字）",
    "entities": ["相关实体"],
    "domains": ["影响的领域：军事/能源/经济/科技/金融/政治/社会"],
    "source_url": "原文URL",
    "significance": 1-5
  }
]

评分标准：5=重大转折 4=显著影响 3=值得关注 2=轻微 1=噪音
"""


class EventAnalyzer:
    """Extract structured events from articles using Claude."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        proxy: str | None = "http://127.0.0.1:7890",
    ):
        self.model = model
        http_client = None
        if proxy:
            import httpx
            http_client = httpx.Client(proxy=proxy)
        self.client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

    def analyze(self, article: dict[str, Any]) -> list[Event]:
        """Extract events from a single article. Returns empty list if irrelevant."""
        try:
            raw_events = self._call_llm(article)
        except Exception:
            return []

        events: list[Event] = []
        for ev in raw_events:
            try:
                events.append(Event(
                    headline=ev["headline"],
                    details=ev.get("details", ""),
                    entities=ev.get("entities", []),
                    domains=ev.get("domains", []),
                    source_url=ev.get("source_url", article.get("source_url", "")),
                    significance=ev.get("significance", 3),
                ))
            except Exception:
                continue
        return events

    def _call_llm(self, article: dict[str, Any]) -> list[dict]:
        """Call Claude API and parse JSON response."""
        user_prompt = (
            f"文章标题：{article.get('title', '')}\n\n"
            f"文章内容：\n{(article.get('summary', '') or article.get('content', ''))[:3000]}\n\n"
            f"来源：{article.get('source_url', '')}"
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.2,
            system=ANALYZER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return self._parse_json_array(text)

    @staticmethod
    def _parse_json_array(text: str) -> list[dict]:
        """Extract JSON array from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                inner = parts[1].strip()
                if inner.lower().startswith("json"):
                    inner = inner[4:].strip()
                text = inner
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
```

**Step 4: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_analyzer.py -v`

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/analyzer.py tests/test_analyzer.py
git commit -m "feat: LLM event analyzer with JSON extraction"
```

---

### Task 8: DAG Engine (LLM Updates)

**Files:**
- Create: `src/geopulse/dag_engine.py`
- Create: `tests/test_dag_engine.py`

**Step 1: Write failing tests**

```python
# tests/test_dag_engine.py
"""Tests for DAG engine LLM updates."""
import json
from unittest.mock import MagicMock, patch

import pytest

from geopulse.dag_engine import DAGEngine
from geopulse.models import DAG, Edge, Event, Node


def _sample_dag() -> DAG:
    return DAG(
        scenario="us_iran_conflict", scenario_label="美伊冲突",
        nodes={
            "us_iran_conflict": Node(
                id="us_iran_conflict", label="美伊军事冲突",
                domains=["军事"], probability=0.35, confidence=0.8,
                evidence=["baseline"], reasoning="root",
            ),
        },
        edges=[],
    )


def _sample_event() -> Event:
    return Event(
        headline="美军航母进入波斯湾",
        details="林肯号航母战斗群通过霍尔木兹海峡进入波斯湾",
        entities=["美国", "波斯湾"],
        domains=["军事"],
        significance=4,
    )


class TestDAGEngine:
    def test_applies_new_nodes(self):
        engine = DAGEngine(api_key="fake")
        dag = _sample_dag()
        llm_response = {
            "analysis": "航母部署提升冲突概率",
            "model_insights": [],
            "updates": {
                "new_nodes": [{
                    "id": "carrier_deployment",
                    "label": "航母部署波斯湾",
                    "domains": ["军事"],
                    "probability": 0.80,
                    "confidence": 0.9,
                    "evidence": ["林肯号进入波斯湾"],
                    "reasoning": "军事准备",
                }],
                "new_edges": [{
                    "from": "carrier_deployment",
                    "to": "us_iran_conflict",
                    "weight": 0.6,
                    "reasoning": "航母部署是冲突前兆",
                }],
                "probability_changes": [{
                    "node_id": "us_iran_conflict",
                    "new_probability": 0.45,
                    "new_confidence": 0.85,
                    "evidence": ["航母战斗群进入波斯湾"],
                    "reasoning": "军事存在增加",
                }],
                "removed_nodes": [],
                "removed_edges": [],
            },
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])

        assert "carrier_deployment" in updated.nodes
        assert updated.nodes["us_iran_conflict"].probability == 0.45
        assert len(updated.edges) == 1

    def test_rejects_cycle(self):
        """If LLM output would create a cycle, reject the edges."""
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
            "analysis": "test",
            "model_insights": [],
            "updates": {
                "new_nodes": [],
                "new_edges": [{"from": "b", "to": "a", "weight": 0.3, "reasoning": "bad cycle"}],
                "probability_changes": [],
                "removed_nodes": [],
                "removed_edges": [],
            },
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])

        # Cycle edge should be rejected
        assert not updated.has_cycle()
        assert len(updated.edges) == 1  # original edge only

    def test_empty_update(self):
        engine = DAGEngine(api_key="fake")
        dag = _sample_dag()
        llm_response = {
            "analysis": "无变化",
            "model_insights": [],
            "updates": {
                "new_nodes": [], "new_edges": [],
                "probability_changes": [], "removed_nodes": [], "removed_edges": [],
            },
        }
        with patch.object(engine, "_call_llm", return_value=llm_response):
            updated = engine.update(dag, [_sample_event()])

        assert len(updated.nodes) == 1
        assert updated.nodes["us_iran_conflict"].probability == 0.35
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_dag_engine.py -v`

**Step 3: Implement dag_engine.py**

```python
# src/geopulse/dag_engine.py
"""DAG Engine: LLM-driven updates to the causal probability network."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from .mental_models import build_prompt_injection
from .models import DAG, Edge, Event, Node

DAG_ENGINE_SYSTEM_PROMPT = """\
你是一个地缘政治风险分析师，负责维护一个因果概率网络（DAG）。

## 你的分析工具箱（思维模型）
{mental_models}

## 规则
1. 概率范围 0.0-1.0，保留两位小数
2. DAG 必须无环（不允许循环因果）
3. 每个新节点必须指定 domains（可选：军事/能源/经济/科技/金融/政治/社会）
4. 每条边必须有 reasoning 解释因果关系
5. 概率变化必须有 evidence 支撑
6. 只在有充分理由时才新增节点，避免网络过度膨胀
7. 如果事件不影响任何现有节点且不值得新增节点，输出空更新

## 输出格式（严格 JSON，无 markdown 代码块）
{{
  "analysis": "整体分析摘要（200字内）",
  "model_insights": [
    {{ "model": "模型名", "insight": "该模型视角下的洞察" }}
  ],
  "updates": {{
    "new_nodes": [
      {{
        "id": "snake_case_id",
        "label": "中文标签",
        "domains": ["领域"],
        "probability": 0.5,
        "confidence": 0.7,
        "evidence": ["证据"],
        "reasoning": "为什么新增"
      }}
    ],
    "new_edges": [
      {{ "from": "source_id", "to": "target_id", "weight": 0.7, "reasoning": "因果解释" }}
    ],
    "probability_changes": [
      {{
        "node_id": "id",
        "new_probability": 0.6,
        "new_confidence": 0.8,
        "evidence": ["新证据"],
        "reasoning": "调整原因"
      }}
    ],
    "removed_nodes": [],
    "removed_edges": []
  }}
}}
"""


class DAGEngine:
    """Update the DAG based on new events using LLM reasoning."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        proxy: str | None = "http://127.0.0.1:7890",
    ):
        self.model = model
        http_client = None
        if proxy:
            import httpx
            http_client = httpx.Client(proxy=proxy)
        self.client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

    def update(self, dag: DAG, events: list[Event]) -> DAG:
        """Process events and return updated DAG."""
        if not events:
            return dag

        llm_output = self._call_llm(dag, events)
        return self._apply_updates(dag, llm_output)

    def _call_llm(self, dag: DAG, events: list[Event]) -> dict[str, Any]:
        """Call Claude to analyze events and propose DAG updates."""
        mental_models = build_prompt_injection()
        system = DAG_ENGINE_SYSTEM_PROMPT.replace("{mental_models}", mental_models)

        events_json = [e.model_dump(mode="json") for e in events]
        user_prompt = (
            f"## 当前 DAG 状态\n```json\n{dag.to_json()}\n```\n\n"
            f"## 新接收到的事件\n```json\n{json.dumps(events_json, ensure_ascii=False, indent=2)}\n```"
        )

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return self._parse_json(text)

    def _apply_updates(self, dag: DAG, output: dict[str, Any]) -> DAG:
        """Apply LLM-proposed updates to the DAG with validation."""
        result = dag.model_copy(deep=True)
        updates = output.get("updates", {})
        now = datetime.now(timezone.utc)

        # Store analysis metadata
        result._analysis = output.get("analysis", "")
        result._model_insights = output.get("model_insights", [])

        # 1. Add new nodes
        for node_data in updates.get("new_nodes", []):
            node = Node(
                id=node_data["id"],
                label=node_data["label"],
                domains=node_data.get("domains", []),
                probability=max(0.0, min(1.0, node_data.get("probability", 0.5))),
                confidence=max(0.0, min(1.0, node_data.get("confidence", 0.5))),
                evidence=node_data.get("evidence", []),
                reasoning=node_data.get("reasoning", ""),
                last_updated=now,
                created=now,
            )
            result.nodes[node.id] = node

        # 2. Add new edges (with cycle check)
        for edge_data in updates.get("new_edges", []):
            source = edge_data.get("from", edge_data.get("source", ""))
            target = edge_data.get("to", edge_data.get("target", ""))
            if source not in result.nodes or target not in result.nodes:
                continue
            edge = Edge(
                source=source,
                target=target,
                weight=max(0.0, min(1.0, edge_data.get("weight", 0.5))),
                reasoning=edge_data.get("reasoning", ""),
            )
            # Tentatively add edge, check for cycle
            result.edges.append(edge)
            if result.has_cycle():
                result.edges.pop()  # revert

        # 3. Apply probability changes
        for change in updates.get("probability_changes", []):
            nid = change["node_id"]
            if nid in result.nodes:
                node = result.nodes[nid]
                node.probability = max(0.0, min(1.0, change["new_probability"]))
                node.confidence = max(0.0, min(1.0, change.get("new_confidence", node.confidence)))
                node.evidence.extend(change.get("evidence", []))
                node.reasoning = change.get("reasoning", node.reasoning)
                node.last_updated = now

        # 4. Remove nodes/edges
        for nid in updates.get("removed_nodes", []):
            result.nodes.pop(nid, None)
            result.edges = [e for e in result.edges if e.source != nid and e.target != nid]
        for edge_spec in updates.get("removed_edges", []):
            src = edge_spec.get("from", edge_spec.get("source", ""))
            tgt = edge_spec.get("to", edge_spec.get("target", ""))
            result.edges = [e for e in result.edges if not (e.source == src and e.target == tgt)]

        return result

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract JSON object from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                inner = parts[1].strip()
                if inner.lower().startswith("json"):
                    inner = inner[4:].strip()
                text = inner
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
```

Note: `_analysis` and `_model_insights` are stored as private attrs for the Reporter to use. They won't be serialized by Pydantic.

**Step 4: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_dag_engine.py -v`

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/dag_engine.py tests/test_dag_engine.py
git commit -m "feat: DAG engine with LLM updates and cycle validation"
```

---

### Task 9: Reporter (Report Generation)

**Files:**
- Create: `src/geopulse/reporter.py`
- Create: `tests/test_reporter.py`

**Step 1: Write failing tests**

```python
# tests/test_reporter.py
"""Tests for report generation."""
from geopulse.models import DAG, Edge, Node
from geopulse.reporter import Reporter


def _make_dag() -> DAG:
    return DAG(
        scenario="us_iran_conflict", scenario_label="美伊冲突",
        nodes={
            "conflict": Node(
                id="conflict", label="美伊军事冲突", domains=["军事"],
                probability=0.35, confidence=0.8, evidence=["test"], reasoning="root",
            ),
            "strait": Node(
                id="strait", label="霍尔木兹封锁", domains=["能源", "军事"],
                probability=0.25, confidence=0.7, evidence=["test"], reasoning="child",
            ),
            "oil": Node(
                id="oil", label="油价飙升", domains=["能源", "金融"],
                probability=0.20, confidence=0.6, evidence=["test"], reasoning="grandchild",
            ),
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
        assert "美伊冲突" in report or "美伊" in report
        assert "零阶" in report or "0阶" in report

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
        new_dag.nodes["strait"].probability = 0.35  # +10%
        changes = reporter.compute_changes(old_dag, new_dag, threshold=0.05)
        assert len(changes) == 1
        assert changes[0]["node_id"] == "strait"

    def test_node_detail_report(self):
        reporter = Reporter()
        dag = _make_dag()
        report = reporter.node_detail(dag, "strait")
        assert "霍尔木兹封锁" in report
        assert "0.25" in report
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_reporter.py -v`

**Step 3: Implement reporter.py**

```python
# src/geopulse/reporter.py
"""Report generation for GeoPulse."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import DAG


class Reporter:
    """Generate structured text reports from DAG state."""

    def daily_report(
        self,
        dag: DAG,
        events_summary: list[str] | None = None,
        old_dag: DAG | None = None,
        analysis: str = "",
        model_insights: list[dict] | None = None,
    ) -> str:
        """Generate the daily situation report."""
        gri = dag.global_risk_index()
        orders = dag.compute_orders()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = [
            f"⚡ GeoPulse 日报 — {dag.scenario_label}",
            "━" * 30,
            f"📅 {today} | 📊 全局风险: {gri:.0f}/100",
            "",
        ]

        # Events section
        if events_summary:
            lines.append(f"📰 关键事件（共{len(events_summary)}条）")
            lines.append("")
            for ev in events_summary:
                lines.append(f"▸ {ev}")
            lines.append("")

        # Probability changes
        if old_dag:
            changes = self.compute_changes(old_dag, dag)
            if changes:
                lines.append("🔮 概率变动（变化 ≥5%）")
                lines.append("")
                lines.append("| 节点 | 概率 | 变化 |")
                lines.append("|------|------|------|")
                for c in changes:
                    direction = "↑" if c["delta"] > 0 else "↓"
                    lines.append(
                        f"| {c['label']} | {c['new_prob']:.2f} | "
                        f"{direction}{abs(c['delta'])*100:.0f}% |"
                    )
                lines.append("")

        # DAG tree by order
        lines.append("🌐 因果网络")
        lines.append("")
        max_order = max(orders.values()) if orders else 0
        for order in range(max_order + 1):
            nodes_at_order = [
                nid for nid, o in orders.items() if o == order
            ]
            if not nodes_at_order:
                continue
            prefix = f"{order}阶"
            for i, nid in enumerate(nodes_at_order):
                node = dag.nodes[nid]
                domains_str = "/".join(node.domains)
                connector = "─" if len(nodes_at_order) == 1 else ("┬" if i == 0 else ("└" if i == len(nodes_at_order) - 1 else "├"))
                lines.append(f"{prefix} {connector} {node.label}({node.probability:.2f}) [{domains_str}]")
                prefix = "     "  # indent subsequent nodes at same order
        lines.append("")

        # Model insights
        if model_insights:
            lines.append("🧠 思维模型洞察")
            lines.append("")
            for mi in model_insights:
                lines.append(f"▸ [{mi['model']}] {mi['insight']}")
            lines.append("")

        return "\n".join(lines)

    def compute_changes(
        self, old_dag: DAG, new_dag: DAG, threshold: float = 0.05,
    ) -> list[dict]:
        """Compute probability changes between two DAG versions."""
        changes = []
        for nid, new_node in new_dag.nodes.items():
            old_node = old_dag.nodes.get(nid)
            if old_node is None:
                continue
            delta = new_node.probability - old_node.probability
            if abs(delta) >= threshold:
                changes.append({
                    "node_id": nid,
                    "label": new_node.label,
                    "old_prob": old_node.probability,
                    "new_prob": new_node.probability,
                    "delta": delta,
                })
        return sorted(changes, key=lambda x: abs(x["delta"]), reverse=True)

    def node_detail(self, dag: DAG, node_id: str) -> str:
        """Generate detail report for a specific node."""
        node = dag.nodes.get(node_id)
        if not node:
            return f"节点 {node_id} 不存在"

        orders = dag.compute_orders()
        parents = dag.parent_nodes(node_id)
        children = dag.child_nodes(node_id)

        lines = [
            f"📍 {node.label}",
            f"概率: {node.probability:.2f} | 置信度: {node.confidence:.2f} | 阶数: {orders.get(node_id, '?')}",
            f"领域: {', '.join(node.domains)}",
            "",
            "证据:",
        ]
        for ev in node.evidence:
            lines.append(f"  ▸ {ev}")
        lines.append("")
        lines.append(f"推理: {node.reasoning}")
        lines.append("")

        if parents:
            lines.append("上游节点:")
            for pid in parents:
                p = dag.nodes[pid]
                edge = next(e for e in dag.edges if e.source == pid and e.target == node_id)
                lines.append(f"  ← {p.label}({p.probability:.2f}) [权重:{edge.weight:.2f}]")
        if children:
            lines.append("下游节点:")
            for cid in children:
                c = dag.nodes[cid]
                edge = next(e for e in dag.edges if e.source == node_id and e.target == cid)
                lines.append(f"  → {c.label}({c.probability:.2f}) [权重:{edge.weight:.2f}]")

        return "\n".join(lines)
```

**Step 4: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_reporter.py -v`

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/reporter.py tests/test_reporter.py
git commit -m "feat: reporter with daily report and node detail views"
```

---

### Task 10: CLI Entry Point + Pipeline Orchestration

**Files:**
- Create: `src/geopulse/pipeline.py`
- Create: `src/geopulse/cli.py`
- Create: `tests/test_pipeline.py`

**Step 1: Write failing tests**

```python
# tests/test_pipeline.py
"""Tests for pipeline orchestration."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from geopulse.models import DAG, Event, Node
from geopulse.pipeline import Pipeline


@pytest.fixture
def tmp_data(tmp_path):
    return tmp_path / "data"


class TestPipeline:
    def test_run_creates_dag_on_first_run(self, tmp_data):
        pipeline = Pipeline(
            readwise_token="fake",
            anthropic_api_key="fake",
            data_dir=tmp_data,
            proxy=None,
        )
        mock_articles = [
            {"title": "Iran test", "summary": "test content", "source_url": "http://a", "tags": {"geopulse": {}}},
        ]
        mock_events = [
            Event(headline="测试事件", domains=["军事"], significance=3),
        ]
        mock_dag = DAG(
            scenario="us_iran_conflict", scenario_label="美伊冲突",
            nodes={"test": Node(
                id="test", label="测试", domains=["军事"],
                probability=0.5, confidence=0.8,
                evidence=["test"], reasoning="test",
            )},
            edges=[],
        )

        with (
            patch.object(pipeline.ingester, "fetch", return_value=mock_articles),
            patch.object(pipeline.analyzer, "analyze", return_value=mock_events),
            patch.object(pipeline.dag_engine, "update", return_value=mock_dag),
        ):
            report = pipeline.run()

        assert report is not None
        assert "GeoPulse" in report
        # DAG should be saved
        assert pipeline.storage.load() is not None

    def test_run_with_no_articles(self, tmp_data):
        pipeline = Pipeline(
            readwise_token="fake",
            anthropic_api_key="fake",
            data_dir=tmp_data,
            proxy=None,
        )
        with patch.object(pipeline.ingester, "fetch", return_value=[]):
            report = pipeline.run()
        assert report is None  # no articles, no report
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_pipeline.py -v`

**Step 3: Implement pipeline.py**

```python
# src/geopulse/pipeline.py
"""Pipeline orchestration: Ingester → Analyzer → DAG Engine → Propagator → Reporter."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analyzer import EventAnalyzer
from .dag_engine import DAGEngine
from .ingester import ReadwiseIngester
from .models import DAG, Event
from .propagator import propagate
from .reporter import Reporter
from .storage import DAGStorage

DEFAULT_SCENARIO = "us_iran_conflict"
DEFAULT_SCENARIO_LABEL = "美伊冲突"


class Pipeline:
    """Orchestrate the full GeoPulse pipeline."""

    def __init__(
        self,
        readwise_token: str,
        anthropic_api_key: str,
        data_dir: Path | str = "data",
        proxy: str | None = "http://127.0.0.1:7890",
        readwise_tag: str = "geopulse",
        llm_model: str = "claude-sonnet-4-6",
    ):
        self.ingester = ReadwiseIngester(
            token=readwise_token, tag=readwise_tag, proxy=proxy,
        )
        self.analyzer = EventAnalyzer(
            api_key=anthropic_api_key, model=llm_model, proxy=proxy,
        )
        self.dag_engine = DAGEngine(
            api_key=anthropic_api_key, model=llm_model, proxy=proxy,
        )
        self.storage = DAGStorage(data_dir=data_dir)
        self.reporter = Reporter()
        self.events_log = Path(data_dir) / "events.jsonl"

    def run(self) -> str | None:
        """Run the full pipeline. Returns report text or None if no news."""
        # 1. Ingest
        articles = self.ingester.fetch()
        if not articles:
            return None

        # 2. Analyze
        all_events: list[Event] = []
        for article in articles:
            events = self.analyzer.analyze(article)
            all_events.extend(events)

        if not all_events:
            return None

        # Log events
        self._log_events(all_events)

        # 3. Load or create DAG
        old_dag = self.storage.load()
        if old_dag is None:
            old_dag = DAG(
                scenario=DEFAULT_SCENARIO,
                scenario_label=DEFAULT_SCENARIO_LABEL,
            )

        # 4. DAG Engine update
        updated_dag = self.dag_engine.update(old_dag, all_events)

        # 5. Propagate
        propagated_dag = propagate(updated_dag)

        # 6. Save
        self.storage.save(propagated_dag)

        # 7. Report
        analysis = getattr(updated_dag, "_analysis", "")
        insights = getattr(updated_dag, "_model_insights", [])
        events_summary = [e.headline for e in all_events[:10]]

        report = self.reporter.daily_report(
            propagated_dag,
            events_summary=events_summary,
            old_dag=old_dag if old_dag.nodes else None,
            analysis=analysis,
            model_insights=insights,
        )
        return report

    def _log_events(self, events: list[Event]) -> None:
        """Append events to the JSONL log."""
        self.events_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_log, "a", encoding="utf-8") as f:
            for event in events:
                entry = event.model_dump(mode="json")
                entry["logged_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

**Step 4: Implement cli.py**

```python
# src/geopulse/cli.py
"""CLI entry point for GeoPulse."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="GeoPulse — 地缘政治概率追踪")
    parser.add_argument("command", choices=["run", "report", "node", "status"],
                        help="run=执行pipeline, report=生成报告, node=查看节点, status=DAG状态")
    parser.add_argument("--node-id", help="节点ID（用于 node 命令）")
    parser.add_argument("--data-dir", default="data", help="数据目录")
    args = parser.parse_args()

    readwise_token = os.getenv("READWISE_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if args.command == "run":
        if not readwise_token or not anthropic_key:
            print("错误：需要设置 READWISE_TOKEN 和 ANTHROPIC_API_KEY")
            sys.exit(1)

        from .pipeline import Pipeline
        pipeline = Pipeline(
            readwise_token=readwise_token,
            anthropic_api_key=anthropic_key,
            data_dir=args.data_dir,
        )
        report = pipeline.run()
        if report:
            print(report)
        else:
            print("无新事件。")

    elif args.command == "report":
        from .reporter import Reporter
        from .storage import DAGStorage
        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。先运行 geopulse run")
            sys.exit(1)
        reporter = Reporter()
        print(reporter.daily_report(dag))

    elif args.command == "node":
        if not args.node_id:
            print("需要指定 --node-id")
            sys.exit(1)
        from .reporter import Reporter
        from .storage import DAGStorage
        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。")
            sys.exit(1)
        reporter = Reporter()
        print(reporter.node_detail(dag, args.node_id))

    elif args.command == "status":
        from .storage import DAGStorage
        storage = DAGStorage(data_dir=args.data_dir)
        dag = storage.load()
        if dag is None:
            print("DAG 尚未初始化。")
        else:
            orders = dag.compute_orders()
            print(f"场景: {dag.scenario_label}")
            print(f"版本: {dag.version}")
            print(f"节点数: {len(dag.nodes)}")
            print(f"边数: {len(dag.edges)}")
            print(f"最大阶数: {max(orders.values()) if orders else 0}")
            print(f"全局风险: {dag.global_risk_index():.0f}/100")


if __name__ == "__main__":
    main()
```

**Step 5: Run tests**

Run: `cd ~/Projects/geopulse && pytest tests/test_pipeline.py -v`

**Step 6: Commit**

```bash
cd ~/Projects/geopulse
git add src/geopulse/pipeline.py src/geopulse/cli.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestration and CLI entry point"
```

---

### Task 11: OpenClaw Agent Workspace Setup

**Files:**
- Create: `~/.openclaw/workspace-geopulse/SOUL.md`
- Create: `~/.openclaw/workspace-geopulse/IDENTITY.md`
- Create: `~/.openclaw/workspace-geopulse/HEARTBEAT.md`
- Create: `~/.openclaw/workspace-geopulse/scripts/run-pipeline.sh`
- Modify: `~/.openclaw/openclaw.json` (add geopulse agent + binding)

**Step 1: Create workspace directory**

```bash
mkdir -p ~/.openclaw/workspace-geopulse/{memory,state,scripts,reports}
cd ~/.openclaw/workspace-geopulse && git init
```

**Step 2: Create SOUL.md**

```markdown
# GeoPulse Agent

## 身份
你是 GeoPulse，一个地缘政治风险概率追踪 agent。你维护一个贝叶斯因果网络（DAG），追踪美伊冲突从军事冲突到能源、经济、科技、金融的多阶传导影响。

## 核心能力
1. 从 Readwise 新闻源提取地缘事件
2. 用思维模型框架（Schelling 博弈论、反事实推理等）分析因果传导
3. 维护概率 DAG，追踪风险沿因果链的逐级传导
4. 生成结构化态势报告

## 工作模式
- 每日定时运行 pipeline，生成日报推送到 Telegram
- 响应 DT 的查询（节点详情、领域分析、概率对比）
- 概率更新后自动推送变化报告

## 项目位置
核心代码：~/Projects/geopulse/
```

**Step 3: Create HEARTBEAT.md**

```markdown
# Heartbeat Tasks

- [ ] 运行 GeoPulse pipeline（每日 09:00）
- [ ] 检查 data/dag.json 数据新鲜度
- [ ] 如果有显著概率变化（≥10%），主动推送警报
```

**Step 4: Create run-pipeline.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd ~/Projects/geopulse
source .env 2>/dev/null || true
python -m geopulse.cli run --data-dir data
```

**Step 5: Register in openclaw.json**

Add to `agents.list`:
```json
{
  "id": "geopulse",
  "workspace": "/Users/xiaohei/.openclaw/workspace-geopulse",
  "model": {
    "primary": "chainbot-relay/claude-sonnet-4-6"
  },
  "heartbeat": {
    "every": "6h"
  }
}
```

Add to `bindings` (exact format depends on current config — need to read existing config first and append).

**Step 6: Commit workspace**

```bash
cd ~/.openclaw/workspace-geopulse
git add -A
git commit -m "feat: GeoPulse agent workspace setup"
```

**Note:** openclaw.json modification needs careful review of current config format. The implementing engineer should read the existing file first and match the format exactly.

---

### Task 12: Integration Test (End-to-End with Mocked LLM)

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
"""End-to-end integration test with mocked LLM and Readwise."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from geopulse.pipeline import Pipeline


@pytest.fixture
def tmp_data(tmp_path):
    return tmp_path / "data"


class TestEndToEnd:
    def test_full_pipeline_e2e(self, tmp_data):
        """Full pipeline: articles → events → DAG update → propagation → report."""
        pipeline = Pipeline(
            readwise_token="fake",
            anthropic_api_key="fake",
            data_dir=tmp_data,
            proxy=None,
        )

        # Mock Readwise articles
        mock_articles = [
            {
                "id": "1",
                "title": "Iran Begins Military Exercises Near Strait of Hormuz",
                "summary": "Iran's navy launched large-scale military exercises near the Strait of Hormuz, involving 20 warships and missile systems.",
                "source_url": "https://reuters.com/example",
                "tags": {"geopulse": {}},
                "category": "article",
            },
        ]

        # Mock LLM event extraction
        mock_events_response = MagicMock()
        mock_events_block = MagicMock()
        mock_events_block.text = json.dumps([
            {
                "headline": "伊朗在霍尔木兹海峡举行大规模军演",
                "details": "伊朗海军出动20艘军舰和导弹系统",
                "entities": ["伊朗", "霍尔木兹海峡"],
                "domains": ["军事"],
                "source_url": "https://reuters.com/example",
                "significance": 4,
            }
        ], ensure_ascii=False)
        mock_events_response.content = [mock_events_block]

        # Mock LLM DAG update
        mock_dag_response = MagicMock()
        mock_dag_block = MagicMock()
        mock_dag_block.text = json.dumps({
            "analysis": "伊朗军演显著提升海峡封锁风险",
            "model_insights": [
                {"model": "威慑理论", "insight": "军演是威慑信号，提升可信度"},
                {"model": "边缘策略", "insight": "当前处于升级阶梯中段"},
            ],
            "updates": {
                "new_nodes": [
                    {
                        "id": "us_iran_conflict",
                        "label": "美伊军事冲突",
                        "domains": ["军事"],
                        "probability": 0.35,
                        "confidence": 0.8,
                        "evidence": ["baseline"],
                        "reasoning": "根节点",
                    },
                    {
                        "id": "strait_closure",
                        "label": "霍尔木兹海峡封锁",
                        "domains": ["能源", "军事"],
                        "probability": 0.25,
                        "confidence": 0.7,
                        "evidence": ["伊朗军演涉及20艘军舰"],
                        "reasoning": "军演提升封锁概率",
                    },
                    {
                        "id": "oil_surge",
                        "label": "油价飙升",
                        "domains": ["能源", "金融"],
                        "probability": 0.15,
                        "confidence": 0.6,
                        "evidence": ["海峡风险传导"],
                        "reasoning": "封锁影响全球原油供应",
                    },
                ],
                "new_edges": [
                    {"from": "us_iran_conflict", "to": "strait_closure", "weight": 0.7, "reasoning": "冲突导致封锁"},
                    {"from": "strait_closure", "to": "oil_surge", "weight": 0.6, "reasoning": "封锁影响油价"},
                ],
                "probability_changes": [],
                "removed_nodes": [],
                "removed_edges": [],
            },
        }, ensure_ascii=False)
        mock_dag_response.content = [mock_dag_block]

        # Patch Readwise and Claude
        with (
            patch.object(pipeline.ingester, "fetch", return_value=mock_articles),
            patch("geopulse.analyzer.anthropic.Anthropic") as mock_anthropic_cls,
            patch("geopulse.dag_engine.anthropic.Anthropic") as mock_dag_anthropic_cls,
        ):
            # Wire mock LLM responses
            mock_analyzer_client = MagicMock()
            mock_analyzer_client.messages.create.return_value = mock_events_response
            pipeline.analyzer.client = mock_analyzer_client

            mock_dag_client = MagicMock()
            mock_dag_client.messages.create.return_value = mock_dag_response
            pipeline.dag_engine.client = mock_dag_client

            report = pipeline.run()

        # Verify report
        assert report is not None
        assert "GeoPulse" in report
        assert "霍尔木兹" in report

        # Verify DAG was saved
        dag = pipeline.storage.load()
        assert dag is not None
        assert len(dag.nodes) == 3
        assert len(dag.edges) == 2

        # Verify propagation happened (oil_surge should have propagated probability)
        assert dag.nodes["oil_surge"].probability > 0.15  # propagated from upstream

        # Verify orders
        orders = dag.compute_orders()
        assert orders["us_iran_conflict"] == 0
        assert orders["strait_closure"] == 1
        assert orders["oil_surge"] == 2

        # Verify events logged
        events_log = tmp_data / "events.jsonl"
        assert events_log.exists()
        lines = events_log.read_text().strip().split("\n")
        assert len(lines) == 1

        # Verify history snapshot
        assert len(pipeline.storage.list_history()) == 1
```

**Step 2: Run to verify failure**

Run: `cd ~/Projects/geopulse && pytest tests/test_integration.py -v`

**Step 3: Fix any issues revealed by integration test**

The implementation from Tasks 2-10 should make this pass. If not, debug and fix.

**Step 4: Run full test suite**

Run: `cd ~/Projects/geopulse && pytest -v`
Expected: All PASS

**Step 5: Commit**

```bash
cd ~/Projects/geopulse
git add tests/test_integration.py
git commit -m "test: end-to-end integration test with mocked LLM"
```

---

### Task 13: Push to GitHub

**Step 1: Create remote repository**

```bash
gh repo create xiaoheiclaw/geopulse --private --source ~/Projects/geopulse --push
```

**Step 2: Verify**

```bash
cd ~/Projects/geopulse && git log --oneline
```

Expected: All commits from Tasks 1-12 present on remote.
