"""Noisy-OR probability propagation on the DAG."""
from __future__ import annotations

from .models import DAG


def propagate(dag: DAG, overrides: dict[str, float] | None = None) -> DAG:
    """Propagate probabilities using Noisy-OR. Returns new DAG (no mutation).
    
    Design:
    - Event nodes (node_type="event", probability >= 0.95): pinned, never overridden.
    - State/prediction nodes: propagated value overrides initial value.
    - If `overrides` dict is provided, those node IDs are pinned to their override values
      (LLM explicit judgment has highest priority).
    - Negative/zero edge weights are clamped to 0.
    """
    result = dag.model_copy(deep=True)
    overrides = overrides or {}

    # Apply overrides first (LLM explicit adjustments)
    for nid, prob in overrides.items():
        if nid in result.nodes:
            result.nodes[nid].probability = max(0.0, min(1.0, prob))

    # Build parent map
    parents_map: dict[str, list[tuple[str, float]]] = {}
    for edge in result.edges:
        weight = max(0.0, min(1.0, edge.weight))
        if weight > 0:
            parents_map.setdefault(edge.target, []).append((edge.source, weight))

    # Pinned nodes: confirmed events + LLM overrides
    pinned = {
        nid for nid, n in result.nodes.items()
        if n.node_type == "event" and n.probability >= 0.95
    }
    pinned.update(overrides.keys())

    # Process in topological order
    for nid in result.topological_sort():
        if nid not in parents_map:
            continue
        if nid in pinned:
            continue

        product = 1.0
        for parent_id, weight in parents_map[nid]:
            parent_prob = result.nodes[parent_id].probability
            product *= (1.0 - parent_prob * weight)
        propagated = 1.0 - product

        result.nodes[nid].probability = round(propagated, 4)

    return result
