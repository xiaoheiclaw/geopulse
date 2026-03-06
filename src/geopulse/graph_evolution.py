"""
GeoPulse v7.4 — Phase 4: Graph Evolution

Agent 提案，代码验证，人类审批（可选）。

Phase 3: process_output — 回写概率 (每轮自动执行)
Phase 4: graph_evolution — 修改结构 (提案制，不自动生效)

Three approval levels by risk:
  L1 (auto): leaf additions, new downstream edges → auto-approve
  L2 (deferred): retype, insert on main path, new S-node → next-run consistency check
  L3 (human): delete, restructure, regime-affecting → pending queue
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import DAG
from .run_output import (
    ApprovalLevel,
    GraphProposal,
    ProposalType,
    ProposalUrgency,
    RunOutput,
)
from .storage import DAGStorage

logger = logging.getLogger(__name__)


# ── Approval Level Classification ────────────────────────────────────

def classify_proposal(proposal: GraphProposal, dag: DAG) -> ApprovalLevel:
    """Classify a proposal into approval level based on risk assessment.

    L1 (auto-approve):
      - add_edge where source exists and target is leaf
      - add_node with type M at leaf layer
      - No regime impact, no deletions

    L2 (deferred + consistency check):
      - add_node with type S or H
      - retype_node
      - add_edge on main path
      - No deletions

    L3 (human review):
      - remove_node, remove_edge
      - restructure_path
      - regime_impact = True
      - Any deletion
    """
    impact = proposal.impact_assessment

    # L3: high risk
    if proposal.type in (ProposalType.remove_node, ProposalType.remove_edge,
                         ProposalType.restructure_path):
        return ApprovalLevel.L3_HUMAN
    if impact.regime_impact:
        return ApprovalLevel.L3_HUMAN

    # L1: low risk leaf additions
    if proposal.type == ProposalType.add_node:
        payload = proposal.payload
        node_type = payload.get("type", payload.get("node_type", "M"))
        if node_type == "M" and not impact.regime_impact and not impact.scenario_impact:
            return ApprovalLevel.L1_AUTO
    if proposal.type == ProposalType.add_edge:
        target_id = proposal.payload.get("target", "")
        if target_id and dag and target_id in dag.nodes:
            # Check if target is a leaf (no outgoing edges)
            outgoing = [e for e in dag.edges if e.source == target_id]
            if not outgoing:
                return ApprovalLevel.L1_AUTO

    # Default: L2
    return ApprovalLevel.L2_DEFERRED


# ── Validation ───────────────────────────────────────────────────────

class ValidationError:
    def __init__(self, proposal_id: str, reason: str):
        self.proposal_id = proposal_id
        self.reason = reason

    def __repr__(self):
        return f"ValidationError({self.proposal_id}: {self.reason})"


def validate_proposal(proposal: GraphProposal, dag: DAG) -> list[ValidationError]:
    """Validate a proposal against current DAG state."""
    errors = []
    pid = proposal.proposal_id

    if proposal.type == ProposalType.add_node:
        node_id = proposal.payload.get("node_id", proposal.target)
        if node_id in dag.nodes:
            errors.append(ValidationError(pid, f"Node '{node_id}' already exists"))
        # Check parents exist
        for parent in proposal.payload.get("parents", []):
            if parent not in dag.nodes:
                errors.append(ValidationError(pid, f"Parent node '{parent}' not found in DAG"))

    elif proposal.type == ProposalType.remove_node:
        if proposal.target not in dag.nodes:
            errors.append(ValidationError(pid, f"Node '{proposal.target}' not found"))
        else:
            # Check it's not a critical path node (has both in and out edges)
            incoming = [e for e in dag.edges if e.target == proposal.target]
            outgoing = [e for e in dag.edges if e.source == proposal.target]
            if incoming and outgoing:
                errors.append(ValidationError(
                    pid,
                    f"Node '{proposal.target}' is on a causal path "
                    f"({len(incoming)} in, {len(outgoing)} out). "
                    f"Use restructure_path instead of remove_node."
                ))

    elif proposal.type == ProposalType.add_edge:
        source = proposal.payload.get("source", "")
        target = proposal.payload.get("target", "")
        if source and source not in dag.nodes:
            errors.append(ValidationError(pid, f"Edge source '{source}' not found"))
        if target and target not in dag.nodes:
            errors.append(ValidationError(pid, f"Edge target '{target}' not found"))
        # Cycle check
        if source and target and source in dag.nodes and target in dag.nodes:
            if _would_create_cycle(dag, source, target):
                errors.append(ValidationError(pid, f"Edge {source}→{target} would create a cycle"))

    elif proposal.type == ProposalType.remove_edge:
        source = proposal.payload.get("source", "")
        target = proposal.payload.get("target", "")
        found = any(e.source == source and e.target == target for e in dag.edges)
        if not found:
            errors.append(ValidationError(pid, f"Edge {source}→{target} not found"))

    elif proposal.type == ProposalType.retype_node:
        if proposal.target not in dag.nodes:
            errors.append(ValidationError(pid, f"Node '{proposal.target}' not found"))

    return errors


def _would_create_cycle(dag: DAG, new_source: str, new_target: str) -> bool:
    """Check if adding new_source→new_target would create a cycle via BFS."""
    # If there's already a path from new_target to new_source, adding this edge creates a cycle
    visited = set()
    queue = [new_target]
    while queue:
        current = queue.pop(0)
        if current == new_source:
            return True
        if current in visited:
            continue
        visited.add(current)
        # Follow existing edges from current
        for edge in dag.edges:
            if edge.source == current and edge.target not in visited:
                queue.append(edge.target)
    return False


# ── Phase 4 Executor ─────────────────────────────────────────────────

class GraphEvolution:
    """Phase 4: Process graph proposals from a RunOutput.

    1. Classify each proposal (L1/L2/L3)
    2. Validate against current DAG
    3. Auto-approve L1, queue L2/L3
    4. Apply approved proposals
    5. Save pending queue for review
    """

    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.pending_file = self.data_dir / "graph_proposals_pending.json"
        self.history_file = self.data_dir / "graph_proposals_history.json"
        self.dag_storage = DAGStorage(data_dir=self.data_dir)

    def process_proposals(self, run_output: RunOutput,
                          auto_apply_l1: bool = True) -> dict:
        """Process all graph proposals from a RunOutput.

        Returns summary dict with applied, pending, rejected counts.
        """
        proposals = run_output.graph_proposals
        if not proposals:
            return {"applied": 0, "pending": 0, "rejected": 0, "errors": []}

        dag = self.dag_storage.load()
        if not dag:
            logger.warning("No DAG loaded, cannot process graph proposals")
            return {"applied": 0, "pending": 0, "rejected": 0,
                    "errors": ["No DAG available"]}

        results = {"applied": 0, "pending": 0, "rejected": 0, "errors": []}
        pending_queue = self._load_pending()
        history = self._load_history()

        for proposal in proposals:
            # 1. Classify
            level = classify_proposal(proposal, dag)
            proposal.approval_level = level
            proposal.auto_approvable = (level == ApprovalLevel.L1_AUTO)

            # 2. Validate
            errors = validate_proposal(proposal, dag)
            if errors:
                proposal.status = "rejected"
                results["rejected"] += 1
                results["errors"].extend([str(e) for e in errors])
                history.append(self._to_record(proposal, run_output.meta.run_id, errors))
                logger.warning(f"Proposal {proposal.proposal_id} rejected: {errors}")
                continue

            # 3. Route by level
            if level == ApprovalLevel.L1_AUTO and auto_apply_l1:
                success = self._apply_proposal(proposal, dag)
                if success:
                    proposal.status = "applied"
                    results["applied"] += 1
                    logger.info(f"L1 auto-applied: {proposal.proposal_id}")
                else:
                    proposal.status = "rejected"
                    results["rejected"] += 1
                    results["errors"].append(f"Failed to apply {proposal.proposal_id}")
            else:
                proposal.status = "pending"
                pending_queue.append(self._to_record(proposal, run_output.meta.run_id))
                results["pending"] += 1
                logger.info(f"L{level.value} queued: {proposal.proposal_id}")

            history.append(self._to_record(proposal, run_output.meta.run_id))

        # Save
        if results["applied"] > 0:
            self.dag_storage.save(dag)
            logger.info(f"DAG saved after {results['applied']} L1 auto-applies")

        self._save_pending(pending_queue)
        self._save_history(history)

        return results

    def review_pending(self) -> list[dict]:
        """Get all pending proposals for human review."""
        return self._load_pending()

    def approve_proposal(self, proposal_id: str) -> bool:
        """Manually approve a pending proposal and apply it."""
        pending = self._load_pending()
        dag = self.dag_storage.load()
        if not dag:
            return False

        for i, record in enumerate(pending):
            if record.get("proposal_id") == proposal_id:
                proposal = self._from_record(record)
                success = self._apply_proposal(proposal, dag)
                if success:
                    pending.pop(i)
                    self._save_pending(pending)
                    self.dag_storage.save(dag)
                    # Update history
                    history = self._load_history()
                    history.append({**record, "status": "applied",
                                    "approved_at": datetime.utcnow().isoformat()})
                    self._save_history(history)
                    return True
                return False
        return False

    def reject_proposal(self, proposal_id: str, reason: str = "") -> bool:
        """Reject a pending proposal."""
        pending = self._load_pending()
        for i, record in enumerate(pending):
            if record.get("proposal_id") == proposal_id:
                pending.pop(i)
                self._save_pending(pending)
                history = self._load_history()
                history.append({**record, "status": "rejected", "reject_reason": reason,
                                "rejected_at": datetime.utcnow().isoformat()})
                self._save_history(history)
                return True
        return False

    # ── Apply logic ──

    def _apply_proposal(self, proposal: GraphProposal, dag: DAG) -> bool:
        """Apply a single proposal to the DAG. Returns success."""
        try:
            if proposal.type == ProposalType.add_node:
                return self._apply_add_node(proposal, dag)
            elif proposal.type == ProposalType.remove_node:
                return self._apply_remove_node(proposal, dag)
            elif proposal.type == ProposalType.add_edge:
                return self._apply_add_edge(proposal, dag)
            elif proposal.type == ProposalType.remove_edge:
                return self._apply_remove_edge(proposal, dag)
            elif proposal.type == ProposalType.retype_node:
                return self._apply_retype_node(proposal, dag)
            else:
                logger.warning(f"Unsupported proposal type: {proposal.type}")
                return False
        except Exception as e:
            logger.error(f"Error applying proposal {proposal.proposal_id}: {e}")
            return False

    def _apply_add_node(self, p: GraphProposal, dag: DAG) -> bool:
        from .models import Node, Edge
        payload = p.payload
        node_id = payload.get("node_id", p.target)
        node = Node(
            id=node_id,
            label=payload.get("label", node_id),
            node_type=payload.get("type", payload.get("node_type", "prediction")),
            domains=payload.get("domains", []),
            probability=payload.get("probability", 0.5),
            confidence=payload.get("confidence", 0.5),
            evidence=payload.get("evidence", []),
            reasoning=p.justification,
        )
        dag.nodes[node_id] = node
        # Add edges from parents
        for parent_id in payload.get("parents", []):
            if parent_id in dag.nodes:
                dag.edges.append(Edge(
                    source=parent_id, target=node_id,
                    weight=payload.get("edge_weight", 0.5),
                    reasoning=f"Phase 4 proposal {p.proposal_id}"
                ))
        # Add edges to children
        for child_id in payload.get("children", []):
            if child_id in dag.nodes:
                dag.edges.append(Edge(
                    source=node_id, target=child_id,
                    weight=payload.get("edge_weight", 0.5),
                    reasoning=f"Phase 4 proposal {p.proposal_id}"
                ))
        dag.version += 1
        return True

    def _apply_remove_node(self, p: GraphProposal, dag: DAG) -> bool:
        node_id = p.target
        if node_id not in dag.nodes:
            return False
        del dag.nodes[node_id]
        dag.edges = [e for e in dag.edges if e.source != node_id and e.target != node_id]
        dag.version += 1
        return True

    def _apply_add_edge(self, p: GraphProposal, dag: DAG) -> bool:
        from .models import Edge
        source = p.payload.get("source", "")
        target = p.payload.get("target", "")
        if not source or not target:
            return False
        dag.edges.append(Edge(
            source=source, target=target,
            weight=p.payload.get("weight", 0.5),
            reasoning=p.justification or f"Phase 4 proposal {p.proposal_id}"
        ))
        dag.version += 1
        return True

    def _apply_remove_edge(self, p: GraphProposal, dag: DAG) -> bool:
        source = p.payload.get("source", "")
        target = p.payload.get("target", "")
        before = len(dag.edges)
        dag.edges = [e for e in dag.edges
                     if not (e.source == source and e.target == target)]
        if len(dag.edges) < before:
            dag.version += 1
            return True
        return False

    def _apply_retype_node(self, p: GraphProposal, dag: DAG) -> bool:
        node_id = p.target
        if node_id not in dag.nodes:
            return False
        new_type = p.payload.get("new_type", p.payload.get("node_type"))
        if new_type:
            dag.nodes[node_id].node_type = new_type
        dag.version += 1
        return True

    # ── Persistence ──

    def _load_pending(self) -> list[dict]:
        if self.pending_file.exists():
            return json.loads(self.pending_file.read_text())
        return []

    def _save_pending(self, data: list[dict]):
        self.pending_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load_history(self) -> list[dict]:
        if self.history_file.exists():
            return json.loads(self.history_file.read_text())
        return []

    def _save_history(self, data: list[dict]):
        # Keep last 200 entries
        self.history_file.write_text(
            json.dumps(data[-200:], indent=2, ensure_ascii=False))

    def _to_record(self, proposal: GraphProposal, run_id: str,
                   errors: list[ValidationError] | None = None) -> dict:
        return {
            "proposal_id": proposal.proposal_id,
            "run_id": run_id,
            "type": proposal.type.value,
            "target": proposal.target,
            "payload": proposal.payload,
            "justification": proposal.justification,
            "source_model": proposal.source_model,
            "approval_level": proposal.approval_level.value,
            "status": proposal.status,
            "urgency": proposal.urgency.value,
            "impact": proposal.impact_assessment.model_dump() if proposal.impact_assessment else {},
            "errors": [str(e) for e in (errors or [])],
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _from_record(self, record: dict) -> GraphProposal:
        from .run_output import ImpactAssessment
        return GraphProposal(
            proposal_id=record["proposal_id"],
            type=record["type"],
            target=record["target"],
            payload=record.get("payload", {}),
            justification=record.get("justification", ""),
            source_model=record.get("source_model", ""),
            approval_level=record.get("approval_level", 2),
            status=record.get("status", "pending"),
            urgency=record.get("urgency", "next_run"),
            impact_assessment=ImpactAssessment(**record.get("impact", {})),
        )
