"""Noisy-OR probability propagation on the DAG."""
from __future__ import annotations

from .models import DAG


def propagate(dag: DAG) -> DAG:
    """Propagate probabilities using Noisy-OR. Returns new DAG (no mutation)."""
    result = dag.model_copy(deep=True)

    # Build parent map: target -> [(parent_id, weight), ...]
    parents_map: dict[str, list[tuple[str, float]]] = {}
    for edge in result.edges:
        parents_map.setdefault(edge.target, []).append((edge.source, edge.weight))

    # Snapshot LLM-assigned probabilities before propagation
    llm_probs = {nid: n.probability for nid, n in result.nodes.items()}

    # Process in topological order so parents are resolved before children
    for nid in result.topological_sort():
        if nid not in parents_map:
            continue

        # Noisy-OR: P = 1 - product(1 - P_parent * weight)
        product = 1.0
        for parent_id, weight in parents_map[nid]:
            parent_prob = result.nodes[parent_id].probability
            product *= (1.0 - parent_prob * weight)
        propagated = 1.0 - product

        # Keep the higher of LLM estimate vs propagated value
        result.nodes[nid].probability = max(llm_probs[nid], round(propagated, 4))

    return result
