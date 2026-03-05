"""Report generation for GeoPulse."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import DAG


class Reporter:
    """Generates human-readable reports from DAG state."""

    def daily_report(
        self,
        dag: DAG,
        events_summary: list[str] | None = None,
        old_dag: DAG | None = None,
        analysis: str = "",
        model_insights: list[dict] | None = None,
    ) -> str:
        """Generate a daily summary report."""
        gri = dag.global_risk_index()
        orders = dag.compute_orders()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = [
            f"⚡ GeoPulse 日报 — {dag.scenario_label}",
            "━" * 30,
            f"📅 {today} | 📊 全局风险: {gri:.0f}/100",
            "",
        ]

        if events_summary:
            lines.append(f"📰 关键事件（共{len(events_summary)}条）")
            lines.append("")
            for ev in events_summary:
                lines.append(f"▸ {ev}")
            lines.append("")

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
                        f"| {c['label']} | {c['new_prob']:.2f} "
                        f"| {direction}{abs(c['delta'])*100:.0f}% |"
                    )
                lines.append("")

        lines.append("🌐 因果网络")
        lines.append("")

        max_order = max(orders.values()) if orders else 0
        for order in range(max_order + 1):
            nodes_at_order = [nid for nid, o in orders.items() if o == order]
            if not nodes_at_order:
                continue
            prefix = f"{order}阶"
            for i, nid in enumerate(nodes_at_order):
                node = dag.nodes[nid]
                domains_str = "/".join(node.domains)
                if len(nodes_at_order) == 1:
                    connector = "─"
                elif i == 0:
                    connector = "┬"
                elif i == len(nodes_at_order) - 1:
                    connector = "└"
                else:
                    connector = "├"
                lines.append(
                    f"{prefix} {connector} {node.label}"
                    f"({node.probability:.2f}) [{domains_str}]"
                )
                prefix = "     "

        lines.append("")

        if model_insights:
            lines.append("🧠 思维模型洞察")
            lines.append("")
            for mi in model_insights:
                lines.append(f"▸ [{mi['model']}] {mi['insight']}")
            lines.append("")

        return "\n".join(lines)

    def compute_changes(
        self, old_dag: DAG, new_dag: DAG, threshold: float = 0.05
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
        """Generate a detailed report for a single node."""
        node = dag.nodes.get(node_id)
        if not node:
            return f"节点 {node_id} 不存在"

        orders = dag.compute_orders()
        parents = dag.parent_nodes(node_id)
        children = dag.child_nodes(node_id)

        lines = [
            f"📍 {node.label}",
            f"概率: {node.probability:.2f} | 置信度: {node.confidence:.2f}"
            f" | 阶数: {orders.get(node_id, '?')}",
            f"领域: {', '.join(node.domains)}",
            "",
            "证据:",
        ]
        for ev in node.evidence:
            lines.append(f"  ▸ {ev}")

        lines.extend(["", f"推理: {node.reasoning}", ""])

        if parents:
            lines.append("上游节点:")
            for pid in parents:
                p = dag.nodes[pid]
                edge = next(
                    e for e in dag.edges if e.source == pid and e.target == node_id
                )
                lines.append(
                    f"  ← {p.label}({p.probability:.2f}) [权重:{edge.weight:.2f}]"
                )

        if children:
            lines.append("下游节点:")
            for cid in children:
                c = dag.nodes[cid]
                edge = next(
                    e for e in dag.edges if e.source == node_id and e.target == cid
                )
                lines.append(
                    f"  → {c.label}({c.probability:.2f}) [权重:{edge.weight:.2f}]"
                )

        return "\n".join(lines)
